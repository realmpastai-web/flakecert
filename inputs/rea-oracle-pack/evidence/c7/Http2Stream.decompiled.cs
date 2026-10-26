using System;
using System.Buffers;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipelines;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Connections;
using Microsoft.AspNetCore.Connections.Features;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Server.Kestrel.Core.Features;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2.FlowControl;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;
using Microsoft.Extensions.Primitives;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2;

internal abstract class Http2Stream : Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpProtocol, IThreadPoolWorkItem, IDisposable, IPooledStream, IHttp2StreamIdFeature, IHttpMinRequestBodyDataRateFeature, IHttpResetFeature, IHttpResponseTrailersFeature, IPersistentStateFeature
{
	[Flags]
	private enum StreamCompletionFlags
	{
		None = 0,
		RstStreamReceived = 1,
		EndStreamReceived = 2,
		Aborted = 4
	}

	private Http2StreamContext _context;

	private Http2OutputProducer _http2Output;

	private StreamInputFlowControl _inputFlowControl;

	private Http2MessageBody _messageBody;

	private bool _decrementCalled;

	private StreamCompletionFlags _completionState;

	private readonly Lock _completionLock = new Lock();

	private IHeaderDictionary _userTrailers;

	private IDictionary<object, object> _persistentState;

	public int TotalParsedHeaderSize { get; set; }

	public Pipe RequestBodyPipe { get; private set; }

	internal long DrainExpirationTimestamp { get; set; }

	public int StreamId => _context.StreamId;

	public BaseConnectionContext ConnectionContext => _context.ConnectionContext;

	public ConnectionMetricsContext MetricsContext => _context.MetricsContext;

	public long? InputRemaining { get; internal set; }

	public bool RequestBodyStarted { get; private set; }

	public bool EndStreamReceived => (_completionState & StreamCompletionFlags.EndStreamReceived) == StreamCompletionFlags.EndStreamReceived;

	private bool IsAborted => (_completionState & StreamCompletionFlags.Aborted) == StreamCompletionFlags.Aborted;

	internal bool RstStreamReceived => (_completionState & StreamCompletionFlags.RstStreamReceived) == StreamCompletionFlags.RstStreamReceived;

	public bool ReceivedEmptyRequestBody
	{
		get
		{
			using (_completionLock.EnterScope())
			{
				return EndStreamReceived && !RequestBodyStarted;
			}
		}
	}

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

	long IPooledStream.PoolExpirationTimestamp => DrainExpirationTimestamp;

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

	int IHttp2StreamIdFeature.StreamId => _context.StreamId;

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

	IDictionary<object, object?> IPersistentStateFeature.State => _persistentState ?? (_persistentState = new ConnectionItems());

	public void Initialize(Http2StreamContext context)
	{
		Initialize((HttpConnectionContext)context);
		_decrementCalled = false;
		_completionState = StreamCompletionFlags.None;
		InputRemaining = null;
		RequestBodyStarted = false;
		DrainExpirationTimestamp = 0L;
		TotalParsedHeaderSize = 0;
		_eagerRequestHeadersParsedLimit = ServerOptions.Limits.MaxRequestHeaderCount * 2;
		_context = context;
		if (_inputFlowControl == null)
		{
			_inputFlowControl = new StreamInputFlowControl(this, context.FrameWriter, context.ConnectionInputFlowControl, context.ServerPeerSettings.InitialWindowSize, context.ServerPeerSettings.InitialWindowSize / 2);
			_http2Output = new Http2OutputProducer(this, context);
			RequestBodyPipe = CreateRequestBodyPipe();
			Output = _http2Output;
		}
		else
		{
			_inputFlowControl.Reset();
			_http2Output.StreamReset(context.ClientPeerSettings.InitialWindowSize);
			RequestBodyPipe.Reset();
		}
	}

	public void InitializeWithExistingContext(int streamId)
	{
		_context.StreamId = streamId;
		Initialize(_context);
	}

	protected override void OnReset()
	{
		_keepAlive = true;
		_userTrailers = null;
		_currentIHttpMinRequestBodyDataRateFeature = this;
		_currentIHttp2StreamIdFeature = this;
		_currentIHttpResponseTrailersFeature = this;
		_currentIHttpResetFeature = this;
		_currentIPersistentStateFeature = this;
	}

	protected override void OnRequestProcessingEnded()
	{
		_http2Output.OnRequestProcessingEnded();
	}

	public void CompleteStream(bool errored)
	{
		try
		{
			if (!EndStreamReceived && !RstStreamReceived)
			{
				if (!errored)
				{
					Log.RequestBodyNotEntirelyRead(ConnectionIdFeature, TraceIdentifier);
				}
				var (streamCompletionFlags, streamCompletionFlags2) = ApplyCompletionFlag(StreamCompletionFlags.Aborted);
				if (streamCompletionFlags != streamCompletionFlags2)
				{
					if (!errored)
					{
						_http2Output.WriteRstStreamAsync(Http2ErrorCode.NO_ERROR).Preserve();
					}
					RequestBodyPipe.Writer.Complete();
				}
			}
			_http2Output.Complete();
			RequestBodyPipe.Reader.Complete();
			_inputFlowControl.Abort();
		}
		finally
		{
			_context.StreamLifetimeHandler.OnStreamCompleted(this);
		}
	}

	protected override string CreateRequestId()
	{
		return StringUtilities.ConcatAsHexSuffix(ConnectionId, ':', (uint)StreamId);
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
			_messageBody = new Http2MessageBody(this);
		}
		return _messageBody;
	}

	protected override bool TryParseRequest(ReadResult result, out bool endConnection)
	{
		endConnection = !TryValidatePseudoHeaders();
		if (TotalParsedHeaderSize > ServerOptions.Limits.MaxRequestHeadersTotalSize)
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
		_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http2;
		if (Method == HttpMethod.None && !TryValidateMethod())
		{
			return false;
		}
		if (!TryValidateAuthorityAndHost(out var hostText))
		{
			return false;
		}
		if (Method == HttpMethod.Connect)
		{
			if (StringValues.IsNullOrEmpty(HttpRequestHeaders.HeaderProtocol))
			{
				if (!StringValues.IsNullOrEmpty(HttpRequestHeaders.HeaderScheme) || !StringValues.IsNullOrEmpty(HttpRequestHeaders.HeaderPath))
				{
					ResetAndAbort(new ConnectionAbortedException(CoreStrings.Http2ErrorConnectMustNotSendSchemeOrPath), Http2ErrorCode.PROTOCOL_ERROR);
					return false;
				}
				RawTarget = hostText;
				return true;
			}
			if (StringValues.IsNullOrEmpty(HttpRequestHeaders.HeaderScheme) || StringValues.IsNullOrEmpty(HttpRequestHeaders.HeaderPath))
			{
				ResetAndAbort(new ConnectionAbortedException(CoreStrings.ConnectRequestsWithProtocolRequireSchemeAndPath), Http2ErrorCode.PROTOCOL_ERROR);
				return false;
			}
			ConnectProtocol = HttpRequestHeaders.HeaderProtocol;
			IsExtendedConnectRequest = true;
		}
		else if (!StringValues.IsNullOrEmpty(HttpRequestHeaders.HeaderProtocol))
		{
			ResetAndAbort(new ConnectionAbortedException(CoreStrings.ProtocolRequiresConnect), Http2ErrorCode.PROTOCOL_ERROR);
			return false;
		}
		string text = HttpRequestHeaders.HeaderScheme.ToString();
		if ((object)text != Scheme && !string.Equals(text, Scheme, StringComparison.OrdinalIgnoreCase))
		{
			if (!ServerOptions.AllowAlternateSchemes || !Uri.CheckSchemeName(text))
			{
				ResetAndAbort(new ConnectionAbortedException(CoreStrings.FormatHttp2StreamErrorSchemeMismatch(text, Scheme)), Http2ErrorCode.PROTOCOL_ERROR);
				return false;
			}
			Scheme = text;
		}
		string text2 = (RawTarget = HttpRequestHeaders.HeaderPath.ToString());
		if (Method == HttpMethod.Options && text2.Length == 1 && text2[0] == '*')
		{
			Path = string.Empty;
			QueryString = string.Empty;
			return true;
		}
		if (_methodText.Length + Scheme.Length + hostText.Length + text2.Length > ServerOptions.Limits.MaxRequestLineSize)
		{
			ResetAndAbort(new ConnectionAbortedException(CoreStrings.BadRequest_RequestLineTooLong), Http2ErrorCode.PROTOCOL_ERROR);
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
		if (Method == HttpMethod.None)
		{
			ResetAndAbort(new ConnectionAbortedException(CoreStrings.FormatHttp2ErrorMethodInvalid(_methodText)), Http2ErrorCode.PROTOCOL_ERROR);
			return false;
		}
		if (Method == HttpMethod.Custom && HttpCharacters.IndexOfInvalidTokenChar(_methodText) >= 0)
		{
			ResetAndAbort(new ConnectionAbortedException(CoreStrings.FormatHttp2ErrorMethodInvalid(_methodText)), Http2ErrorCode.PROTOCOL_ERROR);
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
			ResetAndAbort(new ConnectionAbortedException(CoreStrings.FormatBadRequest_InvalidHostHeader_Detail(hostText)), Http2ErrorCode.PROTOCOL_ERROR);
			return false;
		}
		return true;
	}

	[SkipLocalsInit]
	private bool TryValidatePath(ReadOnlySpan<char> pathSegment)
	{
		if (pathSegment.IsEmpty || pathSegment[0] != '/')
		{
			ResetAndAbort(new ConnectionAbortedException(CoreStrings.FormatHttp2StreamErrorPathInvalid(RawTarget)), Http2ErrorCode.PROTOCOL_ERROR);
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
					ResetAndAbort(new ConnectionAbortedException(CoreStrings.FormatHttp2StreamErrorPathInvalid(RawTarget)), Http2ErrorCode.PROTOCOL_ERROR);
					return false;
				}
				path[i] = (byte)c;
			}
			Path = PathDecoder.DecodePath(path, pathEncoded, RawTarget, QueryString.Length);
			return true;
		}
		catch (InvalidOperationException)
		{
			ResetAndAbort(new ConnectionAbortedException(CoreStrings.FormatHttp2StreamErrorPathInvalid(RawTarget)), Http2ErrorCode.PROTOCOL_ERROR);
			return false;
		}
	}

	public Task OnDataAsync(Http2Frame dataFrame, in ReadOnlySequence<byte> payload)
	{
		if (dataFrame.DataHasPadding)
		{
			OnDataRead(dataFrame.DataPadLength + 1);
		}
		ReadOnlySequence<byte> buffer = payload.Slice(0, dataFrame.DataPayloadLength);
		bool dataEndStream = dataFrame.DataEndStream;
		if (buffer.Length > 0)
		{
			using (_completionLock.EnterScope())
			{
				RequestBodyStarted = true;
				if (dataEndStream)
				{
					_inputFlowControl.StopWindowUpdates();
				}
				_inputFlowControl.Advance((int)buffer.Length);
				if (InputRemaining.HasValue)
				{
					if (buffer.Length > InputRemaining.Value)
					{
						throw new Http2StreamErrorException(StreamId, CoreStrings.Http2StreamErrorMoreDataThanLength, Http2ErrorCode.PROTOCOL_ERROR);
					}
					InputRemaining -= buffer.Length;
				}
				if (!IsAborted)
				{
					buffer.CopyTo(RequestBodyPipe.Writer);
					if (!dataEndStream)
					{
						RequestBodyPipe.Writer.FlushAsync().GetAwaiter().GetResult();
					}
				}
			}
		}
		if (dataEndStream)
		{
			OnEndStreamReceived();
		}
		return Task.CompletedTask;
	}

	public void OnEndStreamReceived()
	{
		ApplyCompletionFlag(StreamCompletionFlags.EndStreamReceived);
		if (InputRemaining.HasValue && InputRemaining.Value != 0L)
		{
			throw new Http2StreamErrorException(StreamId, CoreStrings.Http2StreamErrorLessDataThanLength, Http2ErrorCode.PROTOCOL_ERROR);
		}
		OnTrailersComplete();
		RequestBodyPipe.Writer.Complete();
		_inputFlowControl.StopWindowUpdates();
	}

	public void OnDataRead(int bytesRead)
	{
		_inputFlowControl.UpdateWindows(bytesRead);
	}

	public bool TryUpdateOutputWindow(int bytes)
	{
		return _http2Output.TryUpdateStreamWindow(bytes);
	}

	public void AbortRstStreamReceived()
	{
		DecrementActiveClientStreamCount();
		ApplyCompletionFlag(StreamCompletionFlags.RstStreamReceived);
		Abort(new IOException(CoreStrings.HttpStreamResetByClient));
	}

	public void Abort(IOException abortReason)
	{
		var (streamCompletionFlags, streamCompletionFlags2) = ApplyCompletionFlag(StreamCompletionFlags.Aborted);
		if (streamCompletionFlags != streamCompletionFlags2)
		{
			AbortCore(abortReason);
		}
	}

	protected override void OnErrorAfterResponseStarted()
	{
		ConnectionAbortedException abortReason = new ConnectionAbortedException(CoreStrings.Http2StreamErrorAfterHeaders);
		ResetAndAbort(abortReason, Http2ErrorCode.INTERNAL_ERROR);
	}

	protected override void ApplicationAbort()
	{
		ApplicationAbort(new ConnectionAbortedException(CoreStrings.ConnectionAbortedByApplication), Http2ErrorCode.INTERNAL_ERROR);
	}

	private void ApplicationAbort(ConnectionAbortedException abortReason, Http2ErrorCode error)
	{
		ResetAndAbort(abortReason, error);
	}

	internal void ResetAndAbort(ConnectionAbortedException abortReason, Http2ErrorCode error)
	{
		var (streamCompletionFlags, streamCompletionFlags2) = ApplyCompletionFlag(StreamCompletionFlags.Aborted);
		if (streamCompletionFlags != streamCompletionFlags2)
		{
			Log.Http2StreamResetAbort(TraceIdentifier, error, abortReason);
			DecrementActiveClientStreamCount();
			_http2Output.WriteRstStreamAsync(error).Preserve();
			AbortCore(abortReason);
		}
	}

	private void AbortCore(Exception abortReason)
	{
		_http2Output.Stop();
		CancelRequestAbortedToken();
		PoisonBody(abortReason);
		RequestBodyPipe.Writer.Complete(abortReason);
		_inputFlowControl.Abort();
	}

	public void DecrementActiveClientStreamCount()
	{
		using (_completionLock.EnterScope())
		{
			if (_decrementCalled)
			{
				return;
			}
			_decrementCalled = true;
		}
		_context.StreamLifetimeHandler.DecrementActiveClientStreamCount();
	}

	private Pipe CreateRequestBodyPipe()
	{
		return new Pipe(new PipeOptions(_context.MemoryPool, ServiceContext.Scheduler, PipeScheduler.Inline, _context.ServerPeerSettings.InitialWindowSize + 1, _context.ServerPeerSettings.InitialWindowSize + 1, _context.MemoryPool.GetMinimumSegmentSize(), useSynchronizationContext: false));
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

	public abstract void Execute();

	public void Dispose()
	{
		_http2Output.Dispose();
	}

	public override void OnHeader(int index, bool indexOnly, ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		base.OnHeader(index, indexOnly, name, value);
		if (indexOnly)
		{
			switch (index)
			{
			case 2:
				HttpRequestHeaders.HeaderMethod = HttpMethods.Get;
				Method = HttpMethod.Get;
				_methodText = HttpMethods.Get;
				return;
			case 3:
				HttpRequestHeaders.HeaderMethod = HttpMethods.Post;
				Method = HttpMethod.Post;
				_methodText = HttpMethods.Post;
				return;
			case 6:
				HttpRequestHeaders.HeaderScheme = "http";
				return;
			case 7:
				HttpRequestHeaders.HeaderScheme = "https";
				return;
			}
		}
		if (!HttpRequestHeaders.TryHPackAppend(index, value, !indexOnly))
		{
			AppendHeader(name, value);
		}
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private void AppendHeader(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		HttpRequestHeaders.Append(name, value, checkForNewlineChars: true);
	}

	void IPooledStream.DisposeCore()
	{
		Dispose();
	}

	void IHttpResetFeature.Reset(int errorCode)
	{
		ConnectionAbortedException abortReason = new ConnectionAbortedException(CoreStrings.FormatHttp2StreamResetByApplication((Http2ErrorCode)errorCode));
		ApplicationAbort(abortReason, (Http2ErrorCode)errorCode);
	}
}
