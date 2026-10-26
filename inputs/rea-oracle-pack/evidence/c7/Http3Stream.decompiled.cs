using System;
using System.Buffers;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipelines;
using System.Net.Http;
using System.Net.Http.QPack;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using System.Threading.Tasks.Sources;
using Microsoft.AspNetCore.Connections;
using Microsoft.AspNetCore.Connections.Features;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Internal;
using Microsoft.AspNetCore.Server.Kestrel.Core.Features;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Primitives;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http3;

internal abstract class Http3Stream : Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpProtocol, IHttp3Stream, IHttpStreamHeadersHandler, IThreadPoolWorkItem, IHttpResetFeature, IHttpMinRequestBodyDataRateFeature, IHttpResponseTrailersFeature
{
	private enum HeaderType
	{
		Static,
		StaticAndValue,
		Dynamic,
		NameAndValue
	}

	protected enum RequestHeaderParsingState
	{
		Ready,
		PseudoHeaderFields,
		Headers,
		Body,
		Trailers
	}

	[Flags]
	private enum PseudoHeaderFields
	{
		None = 0,
		Authority = 1,
		Method = 2,
		Path = 4,
		Scheme = 8,
		Status = 0x10,
		Protocol = 0x20,
		Unknown = 0x40000000
	}

	private static class GracefulCloseInitiator
	{
		public const int None = 0;

		public const int Server = 1;

		public const int Client = 2;
	}

	private const PseudoHeaderFields _mandatoryRequestPseudoHeaderFields = PseudoHeaderFields.Method | PseudoHeaderFields.Path | PseudoHeaderFields.Scheme;

	private Http3FrameWriter _frameWriter;

	private Http3OutputProducer _http3Output;

	private Http3StreamContext _context;

	private IProtocolErrorCodeFeature _errorCodeFeature;

	private IStreamIdFeature _streamIdFeature;

	private IStreamAbortFeature _streamAbortFeature;

	private IStreamClosedFeature _streamClosedFeature;

	private PseudoHeaderFields _parsedPseudoHeaderFields;

	private StreamCompletionFlags _completionState;

	private int _isClosed;

	private int _totalParsedHeaderSize;

	private bool _isMethodConnect;

	private bool _isWebTransportSessionAccepted;

	private Http3MessageBody _messageBody;

	private bool _requestBodyStarted;

	private readonly ManualResetValueTaskSource<object> _appCompletedTaskSource = new ManualResetValueTaskSource<object>();

	private readonly Lock _completionLock = new Lock();

	private TaskCompletionSource _abortCompletedTcs;

	protected RequestHeaderParsingState _requestHeaderParsingState;

	private IHeaderDictionary _userTrailers;

	private static ReadOnlySpan<byte> AuthorityBytes => ":authority"u8;

	private static ReadOnlySpan<byte> MethodBytes => ":method"u8;

	private static ReadOnlySpan<byte> PathBytes => ":path"u8;

	private static ReadOnlySpan<byte> ProtocolBytes => ":protocol"u8;

	private static ReadOnlySpan<byte> SchemeBytes => ":scheme"u8;

	private static ReadOnlySpan<byte> StatusBytes => ":status"u8;

	private static ReadOnlySpan<byte> ConnectionBytes => "connection"u8;

	private static ReadOnlySpan<byte> TeBytes => "te"u8;

	private static ReadOnlySpan<byte> TrailersBytes => "trailers"u8;

	private static ReadOnlySpan<byte> ConnectBytes => "CONNECT"u8;

	public bool EndStreamReceived => (_completionState & StreamCompletionFlags.EndStreamReceived) == StreamCompletionFlags.EndStreamReceived;

	public bool IsAborted => (_completionState & StreamCompletionFlags.Aborted) == StreamCompletionFlags.Aborted;

	private bool IsAbortedRead => (_completionState & StreamCompletionFlags.AbortedRead) == StreamCompletionFlags.AbortedRead;

	public bool IsCompleted => (_completionState & StreamCompletionFlags.Completed) == StreamCompletionFlags.Completed;

	public bool CanReuse
	{
		get
		{
			if (!_connectionAborted)
			{
				return HasResponseCompleted;
			}
			return false;
		}
	}

	public bool ReceivedEmptyRequestBody
	{
		get
		{
			using (_completionLock.EnterScope())
			{
				return EndStreamReceived && !_requestBodyStarted;
			}
		}
	}

	public Pipe RequestBodyPipe { get; private set; }

	public long? InputRemaining { get; internal set; }

	public QPackDecoder QPackDecoder { get; private set; }

	public PipeReader Input => _context.Transport.Input;

	public KestrelServerLimits Limits => _context.ServiceContext.ServerOptions.Limits;

	public long StreamId => _streamIdFeature.StreamId;

	public long StreamTimeoutTimestamp { get; set; }

	public bool IsReceivingHeader => _requestHeaderParsingState <= RequestHeaderParsingState.Headers;

	public bool IsDraining => _appCompletedTaskSource.GetStatus() != ValueTaskSourceStatus.Pending;

	public bool IsRequestStream => true;

	public BaseConnectionContext ConnectionContext => _context.ConnectionContext;

	public ConnectionMetricsContext MetricsContext => _context.MetricsContext;

	IHeaderDictionary IHttpResponseTrailersFeature.Trailers
	{
		get
		{
			if (ResponseTrailers == null)
			{
				ResponseTrailers = new HttpResponseTrailers(ServerOptions.ResponseHeaderEncodingSelector);
				if (HasResponseCompleted)
				{
					ResponseTrailers.SetReadOnly();
				}
			}
			return _userTrailers ?? ResponseTrailers;
		}
		set
		{
			ArgumentNullException.ThrowIfNull(value, "value");
			_userTrailers = value;
		}
	}

	MinDataRate? IHttpMinRequestBodyDataRateFeature.MinDataRate
	{
		get
		{
			throw new NotSupportedException(CoreStrings.HttpMinDataRateNotSupported);
		}
		set
		{
			if (value != null)
			{
				throw new NotSupportedException(CoreStrings.HttpMinDataRateNotSupported);
			}
			MinRequestBodyDataRate = value;
		}
	}

	public void Initialize(Http3StreamContext context)
	{
		Initialize((HttpConnectionContext)context);
		InputRemaining = null;
		_context = context;
		_errorCodeFeature = _context.ConnectionFeatures.GetRequiredFeature<IProtocolErrorCodeFeature>();
		_streamIdFeature = _context.ConnectionFeatures.GetRequiredFeature<IStreamIdFeature>();
		_streamAbortFeature = _context.ConnectionFeatures.GetRequiredFeature<IStreamAbortFeature>();
		_streamClosedFeature = _context.ConnectionFeatures.GetRequiredFeature<IStreamClosedFeature>();
		_appCompletedTaskSource.Reset();
		_isClosed = 0;
		_requestHeaderParsingState = RequestHeaderParsingState.Ready;
		_parsedPseudoHeaderFields = PseudoHeaderFields.None;
		_totalParsedHeaderSize = 0;
		_eagerRequestHeadersParsedLimit = ServerOptions.Limits.MaxRequestHeaderCount * 2;
		_isMethodConnect = false;
		_completionState = StreamCompletionFlags.None;
		_abortCompletedTcs = null;
		StreamTimeoutTimestamp = 0L;
		if (_frameWriter == null)
		{
			_frameWriter = new Http3FrameWriter(context.StreamContext, context.TimeoutControl, context.ServiceContext.ServerOptions.Limits.MinResponseDataRate, context.MemoryPool, context.ServiceContext.Log, _streamIdFeature, context.ClientPeerSettings, this);
			_http3Output = new Http3OutputProducer(_frameWriter, context.MemoryPool, this, context.ServiceContext.Log);
			Output = _http3Output;
			RequestBodyPipe = CreateRequestBodyPipe(65536u);
			QPackDecoder = new QPackDecoder(_context.ServiceContext.ServerOptions.Limits.Http3.MaxRequestHeaderFieldSize);
		}
		else
		{
			_http3Output.StreamReset();
			RequestBodyPipe.Reset();
			QPackDecoder.Reset();
		}
		_frameWriter.Reset(context.Transport.Output, context.ConnectionId);
	}

	public void InitializeWithExistingContext(IDuplexPipe transport)
	{
		_context.Transport = transport;
		Initialize(_context);
	}

	public void Abort(ConnectionAbortedException abortReason, Http3ErrorCode errorCode)
	{
		AbortCore(abortReason, errorCode);
	}

	private void AbortCore(Exception exception, Http3ErrorCode errorCode)
	{
		TaskCompletionSource taskCompletionSource;
		using (_completionLock.EnterScope())
		{
			if (IsCompleted || IsAborted)
			{
				return;
			}
			var (streamCompletionFlags, streamCompletionFlags2) = ApplyCompletionFlag(StreamCompletionFlags.Aborted);
			if (streamCompletionFlags == streamCompletionFlags2)
			{
				return;
			}
			taskCompletionSource = (_abortCompletedTcs = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously));
		}
		try
		{
			ConnectionAbortedException ex = exception as ConnectionAbortedException;
			if (ex == null)
			{
				ex = new ConnectionAbortedException(exception.Message, exception);
			}
			_errorCodeFeature.Error = (long)errorCode;
			_context.WebTransportSession?.Abort(ex, errorCode);
			Log.Http3StreamAbort(TraceIdentifier, errorCode, ex);
			_http3Output.Stop();
			CancelRequestAbortedToken();
			PoisonBody(exception);
			RequestBodyPipe.Writer.Complete(exception);
			_frameWriter.Abort(ex);
		}
		finally
		{
			taskCompletionSource.TrySetResult();
		}
	}

	private ValueTask CompleteAndWaitForAbortAsync()
	{
		TaskCompletionSource abortCompletedTcs;
		using (_completionLock.EnterScope())
		{
			_completionState |= StreamCompletionFlags.Completed;
			abortCompletedTcs = _abortCompletedTcs;
		}
		if (abortCompletedTcs != null)
		{
			return new ValueTask(abortCompletedTcs.Task);
		}
		return default;
	}

	protected override void OnErrorAfterResponseStarted()
	{
		ConnectionAbortedException abortReason = new ConnectionAbortedException(CoreStrings.Http3StreamErrorAfterHeaders);
		Abort(abortReason, Http3ErrorCode.InternalError);
	}

	public void OnHeadersComplete(bool endStream)
	{
		OnHeadersComplete();
	}

	public void OnStaticIndexedHeader(int index)
	{
		ref readonly HeaderField reference = ref H3StaticTable.Get(index);
		OnHeaderCore(HeaderType.Static, index, reference.Name, reference.Value);
	}

	public void OnStaticIndexedHeader(int index, ReadOnlySpan<byte> value)
	{
		OnHeaderCore(HeaderType.StaticAndValue, index, H3StaticTable.Get(index).Name, value);
	}

	public void OnDynamicIndexedHeader(int? index, ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		OnHeaderCore(HeaderType.Dynamic, index, name, value);
	}

	public void OnHeader(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		OnHeaderCore(HeaderType.NameAndValue, null, name, value);
	}

	public override void OnHeader(int index, bool indexOnly, ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		base.OnHeader(index, indexOnly, name, value);
		if (indexOnly)
		{
			switch (index)
			{
			case 17:
				HttpRequestHeaders.HeaderMethod = HttpMethods.Get;
				Method = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpMethod.Get;
				_methodText = HttpMethods.Get;
				return;
			case 20:
				HttpRequestHeaders.HeaderMethod = HttpMethods.Post;
				Method = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpMethod.Post;
				_methodText = HttpMethods.Post;
				return;
			case 22:
				HttpRequestHeaders.HeaderScheme = "http";
				return;
			case 23:
				HttpRequestHeaders.HeaderScheme = "https";
				return;
			}
		}
		if (!HttpRequestHeaders.TryQPackAppend(index, value, !indexOnly))
		{
			AppendHeader(name, value);
		}
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private void AppendHeader(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		HttpRequestHeaders.Append(name, value, checkForNewlineChars: true);
	}

	private void OnHeaderCore(HeaderType headerType, int? staticTableIndex, ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		_totalParsedHeaderSize += name.Length + value.Length;
		if (_totalParsedHeaderSize > ServerOptions.Limits.MaxRequestHeadersTotalSize * 2)
		{
			throw new Http3StreamErrorException(CoreStrings.BadRequest_HeadersExceedMaxTotalSize, Http3ErrorCode.RequestRejected);
		}
		try
		{
			if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers)
			{
				UpdateHeaderParsingState(value, GetPseudoHeaderField(name));
				ValidateHeaderContent(name, value);
				OnTrailer(name, value);
				return;
			}
			switch (headerType)
			{
			case HeaderType.Static:
				UpdateHeaderParsingState(value, GetPseudoHeaderField(staticTableIndex.GetValueOrDefault()));
				OnHeader(staticTableIndex.GetValueOrDefault(), indexOnly: true, name, value);
				break;
			case HeaderType.StaticAndValue:
				UpdateHeaderParsingState(value, GetPseudoHeaderField(staticTableIndex.GetValueOrDefault()));
				OnHeader(staticTableIndex.GetValueOrDefault(), indexOnly: false, name, value);
				break;
			case HeaderType.Dynamic:
				if (staticTableIndex.HasValue)
				{
					UpdateHeaderParsingState(value, GetPseudoHeaderField(staticTableIndex.GetValueOrDefault()));
					OnHeader(staticTableIndex.GetValueOrDefault(), indexOnly: false, name, value);
				}
				else
				{
					UpdateHeaderParsingState(value, GetPseudoHeaderField(name));
					OnHeader(name, value, checkForNewlineChars: false);
				}
				break;
			case HeaderType.NameAndValue:
				UpdateHeaderParsingState(value, GetPseudoHeaderField(name));
				ValidateHeaderContent(name, value);
				OnHeader(name, value, checkForNewlineChars: true);
				break;
			}
		}
		catch (Microsoft.AspNetCore.Http.BadHttpRequestException ex)
		{
			throw new Http3StreamErrorException(ex.Message, Http3ErrorCode.MessageError);
		}
		catch (InvalidOperationException)
		{
			throw new Http3StreamErrorException(CoreStrings.BadRequest_MalformedRequestInvalidHeaders, Http3ErrorCode.MessageError);
		}
	}

	private void ValidateHeaderContent(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		if (IsConnectionSpecificHeaderField(name, value))
		{
			throw new Http3StreamErrorException(CoreStrings.HttpErrorConnectionSpecificHeaderField, Http3ErrorCode.MessageError);
		}
		for (int i = 0; i < name.Length; i++)
		{
			if ((uint)(name[i] - 65) <= 25u)
			{
				if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers)
				{
					throw new Http3StreamErrorException(CoreStrings.HttpErrorTrailerNameUppercase, Http3ErrorCode.MessageError);
				}
				throw new Http3StreamErrorException(CoreStrings.HttpErrorHeaderNameUppercase, Http3ErrorCode.MessageError);
			}
		}
	}

	private void UpdateHeaderParsingState(ReadOnlySpan<byte> value, PseudoHeaderFields headerField)
	{
		if (headerField != PseudoHeaderFields.None)
		{
			if (_requestHeaderParsingState == RequestHeaderParsingState.Headers)
			{
				throw new Http3StreamErrorException(CoreStrings.HttpErrorPseudoHeaderFieldAfterRegularHeaders, Http3ErrorCode.MessageError);
			}
			if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers)
			{
				throw new Http3StreamErrorException(CoreStrings.HttpErrorTrailersContainPseudoHeaderField, Http3ErrorCode.MessageError);
			}
			_requestHeaderParsingState = RequestHeaderParsingState.PseudoHeaderFields;
			switch (headerField)
			{
			case PseudoHeaderFields.Unknown:
				throw new Http3StreamErrorException(CoreStrings.HttpErrorUnknownPseudoHeaderField, Http3ErrorCode.MessageError);
			case PseudoHeaderFields.Status:
				throw new Http3StreamErrorException(CoreStrings.HttpErrorResponsePseudoHeaderField, Http3ErrorCode.MessageError);
			}
			if ((_parsedPseudoHeaderFields & headerField) == headerField)
			{
				throw new Http3StreamErrorException(CoreStrings.HttpErrorDuplicatePseudoHeaderField, Http3ErrorCode.MessageError);
			}
			if (headerField == PseudoHeaderFields.Method)
			{
				_isMethodConnect = value.SequenceEqual(ConnectBytes);
			}
			_parsedPseudoHeaderFields |= headerField;
		}
		else if (_requestHeaderParsingState != RequestHeaderParsingState.Trailers)
		{
			_requestHeaderParsingState = RequestHeaderParsingState.Headers;
		}
	}

	private static PseudoHeaderFields GetPseudoHeaderField(int staticTableIndex)
	{
		return staticTableIndex switch
		{
			0 => PseudoHeaderFields.Authority, 
			1 => PseudoHeaderFields.Path, 
			15 => PseudoHeaderFields.Method, 
			16 => PseudoHeaderFields.Method, 
			17 => PseudoHeaderFields.Method, 
			18 => PseudoHeaderFields.Method, 
			19 => PseudoHeaderFields.Method, 
			20 => PseudoHeaderFields.Method, 
			21 => PseudoHeaderFields.Method, 
			22 => PseudoHeaderFields.Scheme, 
			23 => PseudoHeaderFields.Scheme, 
			24 => PseudoHeaderFields.Status, 
			25 => PseudoHeaderFields.Status, 
			26 => PseudoHeaderFields.Status, 
			27 => PseudoHeaderFields.Status, 
			28 => PseudoHeaderFields.Status, 
			63 => PseudoHeaderFields.Status, 
			64 => PseudoHeaderFields.Status, 
			65 => PseudoHeaderFields.Status, 
			66 => PseudoHeaderFields.Status, 
			67 => PseudoHeaderFields.Status, 
			68 => PseudoHeaderFields.Status, 
			69 => PseudoHeaderFields.Status, 
			70 => PseudoHeaderFields.Status, 
			71 => PseudoHeaderFields.Status, 
			_ => PseudoHeaderFields.None, 
		};
	}

	private static PseudoHeaderFields GetPseudoHeaderField(ReadOnlySpan<byte> name)
	{
		if (name.IsEmpty || name[0] != 58)
		{
			return PseudoHeaderFields.None;
		}
		if (name.SequenceEqual(PathBytes))
		{
			return PseudoHeaderFields.Path;
		}
		if (name.SequenceEqual(MethodBytes))
		{
			return PseudoHeaderFields.Method;
		}
		if (name.SequenceEqual(SchemeBytes))
		{
			return PseudoHeaderFields.Scheme;
		}
		if (name.SequenceEqual(StatusBytes))
		{
			return PseudoHeaderFields.Status;
		}
		if (name.SequenceEqual(AuthorityBytes))
		{
			return PseudoHeaderFields.Authority;
		}
		if (name.SequenceEqual(ProtocolBytes))
		{
			return PseudoHeaderFields.Protocol;
		}
		return PseudoHeaderFields.Unknown;
	}

	private static bool IsConnectionSpecificHeaderField(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		if (!name.SequenceEqual(ConnectionBytes))
		{
			if (name.SequenceEqual(TeBytes))
			{
				return !value.SequenceEqual(TrailersBytes);
			}
			return false;
		}
		return true;
	}

	protected override void OnRequestProcessingEnded()
	{
		CompleteStream(errored: false);
	}

	private void CompleteStream(bool errored)
	{
		if (!EndStreamReceived)
		{
			if (!errored)
			{
				Log.RequestBodyNotEntirelyRead(ConnectionIdFeature, TraceIdentifier);
			}
			var (streamCompletionFlags, streamCompletionFlags2) = ApplyCompletionFlag(StreamCompletionFlags.AbortedRead);
			if (streamCompletionFlags != streamCompletionFlags2)
			{
				_streamAbortFeature.AbortRead(256L, new ConnectionAbortedException("The application completed without reading the entire request body."));
				RequestBodyPipe.Writer.Complete();
			}
			TryClose();
		}
		RequestBodyPipe.Reader.Complete();
		_http3Output.Complete();
		_appCompletedTaskSource.SetResult(null);
	}

	private bool TryClose()
	{
		if (Interlocked.Exchange(ref _isClosed, 1) == 0)
		{
			Input.CancelPendingRead();
			return true;
		}
		return false;
	}

	public async Task ProcessRequestAsync<TContext>(IHttpApplication<TContext> application) where TContext : notnull
	{
		Exception error = null;
		_streamClosedFeature.OnClosed((object s) =>
		{
			Http3Stream http3Stream = (Http3Stream)s;
			if (!http3Stream.IsCompleted)
			{
				long error2 = http3Stream._errorCodeFeature.Error;
				if (error2 >= 0)
				{
					http3Stream.AbortCore(new IOException(CoreStrings.HttpStreamResetByClient), (Http3ErrorCode)error2);
				}
			}
		}, this);
		try
		{
			_ = 2;
			try
			{
				Http3RawFrame incomingFrame = new Http3RawFrame();
				bool isContinuedFrame = false;
				while (_isClosed == 0)
				{
					ReadResult result = await Input.ReadAsync();
					ReadOnlySequence<byte> readableBuffer = result.Buffer;
					SequencePosition consumed = readableBuffer.Start;
					SequencePosition examined = readableBuffer.End;
					try
					{
						if (!readableBuffer.IsEmpty)
						{
							ReadOnlySequence<byte> framePayload;
							while (Http3FrameReader.TryReadFrame(ref readableBuffer, incomingFrame, isContinuedFrame, out framePayload))
							{
								if (!isContinuedFrame)
								{
									Log.Http3FrameReceived(ConnectionId, _streamIdFeature.StreamId, incomingFrame);
								}
								SequencePosition end;
								examined = (end = framePayload.End);
								consumed = end;
								await ProcessHttp3Stream(application, incomingFrame, isContinuedFrame, in framePayload, result.IsCompleted && readableBuffer.IsEmpty);
								incomingFrame.RemainingLength -= framePayload.Length;
								isContinuedFrame = incomingFrame.RemainingLength > 0;
							}
						}
						if (!result.IsCompleted)
						{
							goto end_IL_0155;
						}
						await OnEndStreamReceived();
						goto end_IL_0086;
						end_IL_0155:;
					}
					finally
					{
						Input.AdvanceTo(consumed, examined);
					}
				}
				goto end_IL_0075;
				end_IL_0086:;
			}
			catch (Http3StreamErrorException ex)
			{
				error = ex;
				Abort(new ConnectionAbortedException(ex.Message, ex), ex.ErrorCode);
				goto end_IL_0075;
			}
			catch (Http3ConnectionErrorException ex2)
			{
				error = ex2;
				_errorCodeFeature.Error = (long)ex2.ErrorCode;
				_context.StreamLifetimeHandler.OnStreamConnectionError(ex2);
				goto end_IL_0075;
			}
			catch (ConnectionAbortedException ex3)
			{
				error = ex3;
				goto end_IL_0075;
			}
			catch (ConnectionResetException ex4)
			{
				error = ex4;
				long errorCode = ((_errorCodeFeature.Error >= 0) ? _errorCodeFeature.Error : 0);
				AbortCore(new IOException(CoreStrings.HttpStreamResetByClient, ex4), (Http3ErrorCode)errorCode);
				goto end_IL_0075;
			}
			catch (Exception ex5)
			{
				error = ex5;
				Log.LogWarning(0, ex5, "Stream threw an unexpected exception.");
				goto end_IL_0075;
			}
			end_IL_0075:;
		}
		finally
		{
			await Input.CompleteAsync();
			await ((!IsReceivingHeader) ? new ValueTask(_appCompletedTaskSource, _appCompletedTaskSource.Version) : ValueTask.CompletedTask);
			try
			{
				_ = 5;
				try
				{
					await _frameWriter.CompleteAsync();
				}
				catch
				{
					ConnectionAbortedException abortReason = (error as ConnectionAbortedException) ?? new ConnectionAbortedException("The stream has completed.", error);
					Abort(abortReason, Http3ErrorCode.ProtocolError);
					throw;
				}
			}
			finally
			{
				await CompleteAndWaitForAbortAsync();
				await _context.StreamContext.DisposeAsync();
				_context.StreamLifetimeHandler.OnStreamCompleted(this);
				_context.WebTransportSession?.OnClientConnectionClosed();
				if (_context.StreamContext is IDisposable disposable)
				{
					disposable.Dispose();
				}
			}
		}
	}

	private ValueTask OnEndStreamReceived()
	{
		ApplyCompletionFlag(StreamCompletionFlags.EndStreamReceived);
		if (_requestHeaderParsingState == RequestHeaderParsingState.Ready)
		{
			throw new Http3StreamErrorException(CoreStrings.Http3StreamErrorRequestEndedNoHeaders, Http3ErrorCode.RequestIncomplete);
		}
		if (InputRemaining.HasValue && InputRemaining.Value != 0L)
		{
			throw new Http3StreamErrorException(CoreStrings.Http3StreamErrorLessDataThanLength, Http3ErrorCode.ProtocolError);
		}
		_context.WebTransportSession?.OnClientConnectionClosed();
		OnTrailersComplete();
		return RequestBodyPipe.Writer.CompleteAsync();
	}

	private Task ProcessHttp3Stream<TContext>(IHttpApplication<TContext> application, Http3RawFrame incomingFrame, bool isContinuedFrame, in ReadOnlySequence<byte> payload, bool isCompleted)
	{
		Http3FrameType type = incomingFrame.Type;
		if ((ulong)type <= 7uL)
		{
			switch ((int)type)
			{
			case 0:
				return ProcessDataFrameAsync(in payload);
			case 1:
				return ProcessHeadersFrameAsync(application, incomingFrame, isContinuedFrame, payload, isCompleted);
			case 3:
			case 4:
			case 7:
				goto IL_005e;
			case 5:
				throw new Http3ConnectionErrorException(CoreStrings.FormatHttp3ErrorUnsupportedFrameOnServer(incomingFrame.FormattedType), Http3ErrorCode.UnexpectedFrame, ConnectionEndReason.UnexpectedFrame);
			case 2:
			case 6:
				goto IL_0090;
			}
		}
		if (type == Http3FrameType.MaxPushId)
		{
			goto IL_005e;
		}
		goto IL_0090;
		IL_0090:
		return ProcessUnknownFrameAsync();
		IL_005e:
		throw new Http3ConnectionErrorException(CoreStrings.FormatHttp3ErrorUnsupportedFrameOnRequestStream(incomingFrame.FormattedType), Http3ErrorCode.UnexpectedFrame, ConnectionEndReason.UnexpectedFrame);
	}

	private static Task ProcessUnknownFrameAsync()
	{
		return Task.CompletedTask;
	}

	private async Task ProcessHeadersFrameAsync<TContext>(IHttpApplication<TContext> application, Http3RawFrame incomingFrame, bool isContinuedFrame, ReadOnlySequence<byte> payload, bool isCompleted)
	{
		if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers && !isContinuedFrame)
		{
			throw new Http3ConnectionErrorException(CoreStrings.FormatHttp3StreamErrorFrameReceivedAfterTrailers(Http3Formatting.ToFormattedType(Http3FrameType.Headers)), Http3ErrorCode.UnexpectedFrame, ConnectionEndReason.UnexpectedFrame);
		}
		if (_requestHeaderParsingState == RequestHeaderParsingState.Body)
		{
			_requestHeaderParsingState = RequestHeaderParsingState.Trailers;
		}
		try
		{
			bool flag = payload.Length == incomingFrame.RemainingLength;
			QPackDecoder.Decode(in payload, flag, this);
			if (!flag)
			{
				return;
			}
			QPackDecoder.Reset();
		}
		catch (QPackDecodingException ex)
		{
			Log.QPackDecodingError(ConnectionId, StreamId, ex);
			throw new Http3StreamErrorException(ex.Message, Http3ErrorCode.InternalError);
		}
		switch (_requestHeaderParsingState)
		{
		case RequestHeaderParsingState.Ready:
		case RequestHeaderParsingState.PseudoHeaderFields:
			_requestHeaderParsingState = RequestHeaderParsingState.Headers;
			break;
		case RequestHeaderParsingState.Trailers:
			return;
		}
		InputRemaining = HttpRequestHeaders.ContentLength;
		OnHeadersComplete();
		if (isCompleted)
		{
			await OnEndStreamReceived();
		}
		if (_context.ServiceContext.ServerOptions.EnableWebTransportAndH3Datagrams && HttpRequestHeaders.HeaderProtocol.Count > 0)
		{
			if (!_isMethodConnect)
			{
				throw new Http3StreamErrorException(CoreStrings.Http3MethodMustBeConnectWhenUsingProtocolPseudoHeader, Http3ErrorCode.ProtocolError);
			}
			if (!_parsedPseudoHeaderFields.HasFlag(PseudoHeaderFields.Authority) || !_parsedPseudoHeaderFields.HasFlag(PseudoHeaderFields.Path))
			{
				throw new Http3StreamErrorException(CoreStrings.Http3MissingAuthorityOrPathPseudoHeaders, Http3ErrorCode.ProtocolError);
			}
			if (_context.ClientPeerSettings.EnableWebTransport != _context.ServerPeerSettings.EnableWebTransport)
			{
				throw new Http3StreamErrorException(CoreStrings.FormatHttp3WebTransportStatusMismatch(_context.ClientPeerSettings.EnableWebTransport == 1, _context.ServerPeerSettings.EnableWebTransport == 1), Http3ErrorCode.SettingsError);
			}
			if (_context.ClientPeerSettings.H3Datagram != _context.ServerPeerSettings.H3Datagram)
			{
				throw new Http3StreamErrorException(CoreStrings.FormatHttp3DatagramStatusMismatch(_context.ClientPeerSettings.H3Datagram == 1, _context.ServerPeerSettings.H3Datagram == 1), Http3ErrorCode.SettingsError);
			}
			if (string.Equals(HttpRequestHeaders.HeaderProtocol, "webtransport", StringComparison.Ordinal) && ((IDictionary<string, StringValues>)HttpRequestHeaders).TryGetValue("sec-webtransport-http3-draft02", out StringValues value) && string.Equals(value, "1", StringComparison.Ordinal))
			{
				IsWebTransportRequest = true;
			}
		}
		else if (!_isMethodConnect && (_parsedPseudoHeaderFields & (PseudoHeaderFields.Method | PseudoHeaderFields.Path | PseudoHeaderFields.Scheme)) != (PseudoHeaderFields.Method | PseudoHeaderFields.Path | PseudoHeaderFields.Scheme))
		{
			throw new Http3StreamErrorException(CoreStrings.HttpErrorMissingMandatoryPseudoHeaderFields, Http3ErrorCode.MessageError);
		}
		_requestHeaderParsingState = RequestHeaderParsingState.Body;
		StreamTimeoutTimestamp = 0L;
		_context.StreamLifetimeHandler.OnStreamHeaderReceived(this);
		ThreadPool.UnsafeQueueUserWorkItem(this, preferLocal: false);
	}

	private Task ProcessDataFrameAsync(in ReadOnlySequence<byte> payload)
	{
		if (_requestHeaderParsingState == RequestHeaderParsingState.Ready)
		{
			throw new Http3ConnectionErrorException(CoreStrings.Http3StreamErrorDataReceivedBeforeHeaders, Http3ErrorCode.UnexpectedFrame, ConnectionEndReason.UnexpectedFrame);
		}
		if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers)
		{
			throw new Http3ConnectionErrorException(CoreStrings.FormatHttp3StreamErrorFrameReceivedAfterTrailers(Http3Formatting.ToFormattedType(Http3FrameType.Data)), Http3ErrorCode.UnexpectedFrame, ConnectionEndReason.UnexpectedFrame);
		}
		if (InputRemaining.HasValue)
		{
			if (payload.Length > InputRemaining.Value)
			{
				throw new Http3StreamErrorException(CoreStrings.Http3StreamErrorMoreDataThanLength, Http3ErrorCode.ProtocolError);
			}
			InputRemaining -= payload.Length;
		}
		using (_completionLock.EnterScope())
		{
			if (IsAborted || IsAbortedRead)
			{
				return Task.CompletedTask;
			}
			_requestBodyStarted = true;
			foreach (ReadOnlyMemory<byte> item in payload)
			{
				RequestBodyPipe.Writer.Write(item.Span);
			}
			return RequestBodyPipe.Writer.FlushAsync().GetAsTask();
		}
	}

	protected override void OnReset()
	{
		_keepAlive = true;
		_userTrailers = null;
		_isWebTransportSessionAccepted = false;
		_isMethodConnect = false;
		_currentIHttpMinRequestBodyDataRateFeature = this;
		_currentIHttpResponseTrailersFeature = this;
		_currentIHttpResetFeature = this;
	}

	protected override void ApplicationAbort()
	{
		ApplicationAbort(new ConnectionAbortedException(CoreStrings.ConnectionAbortedByApplication), Http3ErrorCode.InternalError);
	}

	private void ApplicationAbort(ConnectionAbortedException abortReason, Http3ErrorCode error)
	{
		Abort(abortReason, error);
	}

	protected override string CreateRequestId()
	{
		return _context.StreamContext.ConnectionId;
	}

	protected override MessageBody CreateMessageBody()
	{
		if (ReceivedEmptyRequestBody)
		{
			return MessageBody.ZeroContentLengthClose;
		}
		if (_messageBody != null)
		{
			_messageBody.Reset();
		}
		else
		{
			_messageBody = new Http3MessageBody(this);
		}
		return _messageBody;
	}

	protected override bool TryParseRequest(ReadResult result, out bool endConnection)
	{
		endConnection = !TryValidatePseudoHeaders();
		if (_totalParsedHeaderSize > ServerOptions.Limits.MaxRequestHeadersTotalSize)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.HeadersExceedMaxTotalSize);
		}
		if (RequestHeadersParsed > ServerOptions.Limits.MaxRequestHeaderCount)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.TooManyHeaders);
		}
		HttpRequestHeaders.ClearPseudoRequestHeaders();
		HttpRequestHeaders.MergeCookies();
		return true;
	}

	private bool TryValidatePseudoHeaders()
	{
		_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http3;
		if (!TryValidateMethod())
		{
			return false;
		}
		if (!TryValidateAuthorityAndHost(out var hostText))
		{
			return false;
		}
		if (Method == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpMethod.Connect && HttpRequestHeaders.HeaderProtocol.Count == 0)
		{
			if (!string.IsNullOrEmpty(HttpRequestHeaders.HeaderScheme) || !string.IsNullOrEmpty(HttpRequestHeaders.HeaderPath))
			{
				Abort(new ConnectionAbortedException(CoreStrings.Http3ErrorConnectMustNotSendSchemeOrPath), Http3ErrorCode.ProtocolError);
				return false;
			}
			RawTarget = hostText;
			return true;
		}
		string text = HttpRequestHeaders.HeaderScheme.ToString();
		if ((object)text != Scheme && !string.Equals(text, Scheme, StringComparison.OrdinalIgnoreCase))
		{
			if (!ServerOptions.AllowAlternateSchemes || !Uri.CheckSchemeName(text))
			{
				string message = CoreStrings.FormatHttp3StreamErrorSchemeMismatch(text, Scheme);
				Abort(new ConnectionAbortedException(message), Http3ErrorCode.ProtocolError);
				return false;
			}
			Scheme = text;
		}
		string text2 = (RawTarget = HttpRequestHeaders.HeaderPath.ToString());
		if (Method == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpMethod.Options && text2.Length == 1 && text2[0] == '*')
		{
			Path = string.Empty;
			QueryString = string.Empty;
			return true;
		}
		if (_methodText.Length + Scheme.Length + hostText.Length + text2.Length > ServerOptions.Limits.MaxRequestLineSize)
		{
			Abort(new ConnectionAbortedException(CoreStrings.BadRequest_RequestLineTooLong), Http3ErrorCode.RequestRejected);
			return false;
		}
		int num = text2.IndexOf('?');
		QueryString = ((num == -1) ? string.Empty : text2.Substring(num));
		ReadOnlySpan<char> pathSegment = ((num == -1) ? ((ReadOnlySpan<char>)text2) : text2.AsSpan(0, num));
		return TryValidatePath(pathSegment);
	}

	private bool TryValidateMethod()
	{
		_methodText = HttpRequestHeaders.HeaderMethod.ToString();
		Method = HttpUtilities.GetKnownMethod(_methodText);
		if (Method == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpMethod.None)
		{
			Abort(new ConnectionAbortedException(CoreStrings.FormatHttp3ErrorMethodInvalid(_methodText)), Http3ErrorCode.ProtocolError);
			return false;
		}
		if (Method == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpMethod.Custom && HttpCharacters.IndexOfInvalidTokenChar(_methodText) >= 0)
		{
			Abort(new ConnectionAbortedException(CoreStrings.FormatHttp3ErrorMethodInvalid(_methodText)), Http3ErrorCode.ProtocolError);
			return false;
		}
		return true;
	}

	private bool TryValidateAuthorityAndHost(out string hostText)
	{
		StringValues headerAuthority = HttpRequestHeaders.HeaderAuthority;
		StringValues stringValues = HttpRequestHeaders.HeaderHost;
		if (!StringValues.IsNullOrEmpty(headerAuthority))
		{
			HttpRequestHeaders.HeaderHost = headerAuthority;
			stringValues = headerAuthority;
		}
		hostText = stringValues.ToString();
		if (stringValues.Count > 1 || !HttpUtilities.IsHostHeaderValid(hostText))
		{
			Abort(new ConnectionAbortedException(CoreStrings.FormatBadRequest_InvalidHostHeader_Detail(hostText)), Http3ErrorCode.ProtocolError);
			return false;
		}
		return true;
	}

	[SkipLocalsInit]
	private bool TryValidatePath(ReadOnlySpan<char> pathSegment)
	{
		if (pathSegment.IsEmpty || pathSegment[0] != '/')
		{
			Abort(new ConnectionAbortedException(CoreStrings.FormatHttp3StreamErrorPathInvalid(RawTarget)), Http3ErrorCode.ProtocolError);
			return false;
		}
		bool pathEncoded = pathSegment.Contains('%');
		try
		{
			Span<byte> span = ((pathSegment.Length > 256) ? ((Span<byte>)new byte[pathSegment.Length]) : stackalloc byte[256].Slice(0, pathSegment.Length));
			Span<byte> path = span;
			for (int i = 0; i < pathSegment.Length; i++)
			{
				char c = pathSegment[i];
				if (c > 'ÿ')
				{
					Abort(new ConnectionAbortedException(CoreStrings.FormatHttp3StreamErrorPathInvalid(RawTarget)), Http3ErrorCode.ProtocolError);
					return false;
				}
				path[i] = (byte)c;
			}
			Path = PathDecoder.DecodePath(path, pathEncoded, RawTarget, QueryString.Length);
			return true;
		}
		catch (InvalidOperationException)
		{
			Abort(new ConnectionAbortedException(CoreStrings.FormatHttp3StreamErrorPathInvalid(RawTarget)), Http3ErrorCode.ProtocolError);
			return false;
		}
	}

	private Pipe CreateRequestBodyPipe(uint windowSize)
	{
		return new Pipe(new PipeOptions(_context.MemoryPool, ServiceContext.Scheduler, PipeScheduler.Inline, windowSize + 1, windowSize + 1, _context.MemoryPool.GetMinimumSegmentSize(), useSynchronizationContext: false));
	}

	private (StreamCompletionFlags OldState, StreamCompletionFlags NewState) ApplyCompletionFlag(StreamCompletionFlags completionState)
	{
		using (_completionLock.EnterScope())
		{
			StreamCompletionFlags completionState2 = _completionState;
			_completionState |= completionState;
			return (OldState: completionState2, NewState: _completionState);
		}
	}

	public override async ValueTask<IWebTransportSession> AcceptAsync(CancellationToken token)
	{
		if (_isWebTransportSessionAccepted)
		{
			throw new InvalidOperationException(CoreStrings.AcceptCannotBeCalledMultipleTimes);
		}
		if (!_context.ServiceContext.ServerOptions.EnableWebTransportAndH3Datagrams)
		{
			throw new InvalidOperationException(CoreStrings.WebTransportIsDisabled);
		}
		if (!IsWebTransportRequest)
		{
			throw new InvalidOperationException(CoreStrings.FormatFailedToNegotiateCommonWebTransportVersion("sec-webtransport-http3-draft02"));
		}
		_isWebTransportSessionAccepted = true;
		string text = "draft02";
		_context.WebTransportSession = _context.Connection.OpenNewWebTransportSession(this);
		ResponseHeaders["sec-webtransport-http3-draft"] = text;
		await FlushAsync(token);
		return _context.WebTransportSession;
	}

	public abstract void Execute();

	public void Abort()
	{
		Abort(new ConnectionAbortedException(), Http3ErrorCode.RequestCancelled);
	}

	void IHttpResetFeature.Reset(int errorCode)
	{
		ConnectionAbortedException abortReason = new ConnectionAbortedException(CoreStrings.FormatHttp3StreamResetByApplication(Http3Formatting.ToFormattedErrorCode((Http3ErrorCode)errorCode)));
		ApplicationAbort(abortReason, (Http3ErrorCode)errorCode);
	}
}
