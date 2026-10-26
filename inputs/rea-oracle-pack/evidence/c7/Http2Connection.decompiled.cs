using System;
using System.Buffers;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipelines;
using System.Net.Http;
using System.Net.Http.HPack;
using System.Security.Authentication;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Connections;
using Microsoft.AspNetCore.Connections.Features;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Internal;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2.FlowControl;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;
using Microsoft.Extensions.Logging;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2;

internal sealed class Http2Connection : IHttp2StreamLifetimeHandler, IHttpStreamHeadersHandler, IRequestProcessor
{
	[Flags]
	private enum ReadPrefaceState
	{
		None = 0,
		Preface = 1,
		Http1x = 2,
		All = Preface | Http1x
	}

	private enum HeaderType
	{
		Static,
		StaticAndValue,
		Dynamic,
		NameAndValue
	}

	private enum RequestHeaderParsingState
	{
		Ready,
		PseudoHeaderFields,
		Headers,
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

	public static byte[]? InvalidHttp1xErrorResponseBytes;

	private const PseudoHeaderFields _mandatoryRequestPseudoHeaderFields = PseudoHeaderFields.Method | PseudoHeaderFields.Path | PseudoHeaderFields.Scheme;

	private const int InitialStreamPoolSize = 5;

	private const int MaxStreamPoolSize = 100;

	private readonly TimeSpan StreamPoolExpiry = TimeSpan.FromSeconds(5L);

	private const string MaximumEnhanceYourCalmCountProperty = "Microsoft.AspNetCore.Server.Kestrel.Http2.MaxEnhanceYourCalmCount";

	internal static readonly int EnhanceYourCalmMaximumCount = GetMaximumEnhanceYourCalmCount();

	internal const int EnhanceYourCalmTickWindowCount = 5;

	private readonly HttpConnectionContext _context;

	private readonly ConnectionMetricsContext _metricsContext;

	private readonly IConnectionMetricsTagsFeature _metricsTagsFeature;

	private readonly Http2FrameWriter _frameWriter;

	private readonly Pipe _input;

	private readonly Task _inputTask;

	private readonly int _minAllocBufferSize;

	private readonly HPackDecoder _hpackDecoder;

	private readonly InputFlowControl _inputFlowControl;

	private readonly Http2PeerSettings _serverSettings = new Http2PeerSettings();

	private readonly Http2PeerSettings _clientSettings = new Http2PeerSettings();

	private readonly Http2Frame _incomingFrame = new Http2Frame();

	private readonly bool _scheduleInline;

	private Http2Stream _currentHeadersStream;

	private RequestHeaderParsingState _requestHeaderParsingState;

	private PseudoHeaderFields _parsedPseudoHeaderFields;

	private Http2HeadersFrameFlags _headerFlags;

	private int _totalParsedHeaderSize;

	private bool _isMethodConnect;

	private int _highestOpenedStreamId;

	private bool _gracefulCloseStarted;

	private int _clientActiveStreamCount;

	private int _serverActiveStreamCount;

	private int _enhanceYourCalmCount;

	private int _tickCount;

	private readonly ConcurrentQueue<Http2Stream> _completedStreams = new ConcurrentQueue<Http2Stream>();

	private readonly StreamCloseAwaitable _streamCompletionAwaitable = new StreamCloseAwaitable();

	private int _gracefulCloseInitiator;

	private ConnectionEndReason _gracefulCloseReason;

	private int _isClosed;

	internal readonly Http2KeepAlive? _keepAlive;

	internal readonly Dictionary<int, Http2Stream> _streams = new Dictionary<int, Http2Stream>();

	internal PooledStreamStack<Http2Stream> StreamPool;

	internal IHttp2StreamLifetimeHandler _streamLifetimeHandler;

	private static ReadOnlySpan<byte> ClientPrefaceBytes => "PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"u8;

	private static ReadOnlySpan<byte> AuthorityBytes => ":authority"u8;

	private static ReadOnlySpan<byte> MethodBytes => ":method"u8;

	private static ReadOnlySpan<byte> PathBytes => ":path"u8;

	private static ReadOnlySpan<byte> SchemeBytes => ":scheme"u8;

	private static ReadOnlySpan<byte> StatusBytes => ":status"u8;

	private static ReadOnlySpan<byte> ConnectionBytes => "connection"u8;

	private static ReadOnlySpan<byte> TeBytes => "te"u8;

	private static ReadOnlySpan<byte> TrailersBytes => "trailers"u8;

	private static ReadOnlySpan<byte> ConnectBytes => "CONNECT"u8;

	private static ReadOnlySpan<byte> ProtocolBytes => ":protocol"u8;

	public static ReadOnlySpan<byte> ClientPreface => ClientPrefaceBytes;

	private static bool IsEnhanceYourCalmLimitEnabled => EnhanceYourCalmMaximumCount > 0;

	internal bool SendEnhanceYourCalmOnStartStream { private get; set; }

	public string ConnectionId => _context.ConnectionId;

	public PipeReader Input => _input.Reader;

	public KestrelTrace Log => _context.ServiceContext.Log;

	public IFeatureCollection ConnectionFeatures => _context.ConnectionFeatures;

	public TimeProvider TimeProvider => _context.ServiceContext.TimeProvider;

	public ITimeoutControl TimeoutControl => _context.TimeoutControl;

	public KestrelServerLimits Limits => _context.ServiceContext.ServerOptions.Limits;

	internal Http2PeerSettings ServerSettings => _serverSettings;

	internal uint MaxTrackedStreams => Math.Max(_serverSettings.MaxConcurrentStreams * 2, 100u);

	private static int GetMaximumEnhanceYourCalmCount()
	{
		object data = AppContext.GetData("Microsoft.AspNetCore.Server.Kestrel.Http2.MaxEnhanceYourCalmCount");
		if (data is int)
		{
			return (int)data;
		}
		if (data is string s && int.TryParse(s, out var result))
		{
			return result;
		}
		return 20;
	}

	public Http2Connection(HttpConnectionContext context)
	{
		KestrelServerLimits limits = context.ServiceContext.ServerOptions.Limits;
		Http2Limits http = limits.Http2;
		_context = context;
		_streamLifetimeHandler = this;
		_metricsContext = context.MetricsContext;
		_metricsTagsFeature = context.ConnectionFeatures.Get<IConnectionMetricsTagsFeature>();
		_context.InitialExecutionContext = ExecutionContext.Capture();
		_input = new Pipe(GetInputPipeOptions());
		_minAllocBufferSize = context.MemoryPool.GetMinimumAllocSize();
		_hpackDecoder = new HPackDecoder(http.HeaderTableSize, http.MaxRequestHeaderFieldSize);
		uint initialConnectionWindowSize = (uint)http.InitialConnectionWindowSize;
		_inputFlowControl = new InputFlowControl(initialConnectionWindowSize, initialConnectionWindowSize / 2);
		if (http.KeepAlivePingDelay != TimeSpan.MaxValue)
		{
			_keepAlive = new Http2KeepAlive(http.KeepAlivePingDelay, http.KeepAlivePingTimeout, context.ServiceContext.TimeProvider);
		}
		_serverSettings.MaxConcurrentStreams = (uint)http.MaxStreamsPerConnection;
		_serverSettings.MaxFrameSize = (uint)http.MaxFrameSize;
		_serverSettings.HeaderTableSize = (uint)http.HeaderTableSize;
		_serverSettings.MaxHeaderListSize = (uint)limits.MaxRequestHeadersTotalSize;
		_serverSettings.InitialWindowSize = (uint)http.InitialStreamWindowSize;
		StreamPool = new PooledStreamStack<Http2Stream>(Math.Min(5, http.MaxStreamsPerConnection));
		_scheduleInline = context.ServiceContext.Scheduler == PipeScheduler.Inline;
		_inputTask = CopyPipeAsync(_context.Transport.Input, _input.Writer);
		_frameWriter = new Http2FrameWriter(context.Transport.Output, context.ConnectionContext, this, (int)Math.Min(MaxTrackedStreams, 2147483647u), context.TimeoutControl, limits.MinResponseDataRate, context.ConnectionId, context.MemoryPool, context.ServiceContext);
	}

	public void OnInputOrOutputCompleted()
	{
		bool flag = _clientActiveStreamCount != 0;
		if (TryClose())
		{
			SetConnectionErrorCode(flag ? ConnectionEndReason.ConnectionReset : ConnectionEndReason.TransportCompleted, Http2ErrorCode.NO_ERROR);
		}
		bool flag2 = _context.ServiceContext.ServerOptions.FinOnError | flag;
		_frameWriter.Abort(flag2 ? new ConnectionAbortedException(CoreStrings.ConnectionAbortedByClient) : null);
	}

	private void SetConnectionErrorCode(ConnectionEndReason reason, Http2ErrorCode errorCode)
	{
		KestrelMetrics.AddConnectionEndReason(_metricsContext, reason);
	}

	public void Abort(ConnectionAbortedException ex, ConnectionEndReason reason)
	{
		Abort(ex, Http2ErrorCode.INTERNAL_ERROR, reason);
	}

	public void Abort(ConnectionAbortedException ex, Http2ErrorCode errorCode, ConnectionEndReason reason)
	{
		if (TryClose())
		{
			SetConnectionErrorCode(reason, errorCode);
			_frameWriter.WriteGoAwayAsync(int.MaxValue, errorCode).Preserve();
		}
		_frameWriter.Abort(ex);
	}

	public void StopProcessingNextRequest(ConnectionEndReason reason)
	{
		StopProcessingNextRequest(serverInitiated: true, reason);
	}

	public void HandleRequestHeadersTimeout()
	{
		Log.ConnectionBadRequest(ConnectionId, KestrelBadHttpRequestException.GetException(RequestRejectionReason.RequestHeadersTimeout));
		Abort(new ConnectionAbortedException(CoreStrings.BadRequest_RequestHeadersTimeout), Http2ErrorCode.INTERNAL_ERROR, ConnectionEndReason.RequestHeadersTimeout);
	}

	public void HandleReadDataRateTimeout()
	{
		Log.RequestBodyMinimumDataRateNotSatisfied(ConnectionId, null, Limits.MinRequestBodyDataRate.BytesPerSecond);
		Abort(new ConnectionAbortedException(CoreStrings.BadRequest_RequestBodyTimeout), Http2ErrorCode.INTERNAL_ERROR, ConnectionEndReason.MinRequestBodyDataRate);
	}

	public void StopProcessingNextRequest(bool serverInitiated, ConnectionEndReason reason)
	{
		int value = (serverInitiated ? 1 : 2);
		if (Interlocked.CompareExchange(ref _gracefulCloseInitiator, value, 0) == 0)
		{
			_gracefulCloseReason = reason;
			Input.CancelPendingRead();
		}
	}

	public async Task ProcessRequestsAsync<TContext>(IHttpApplication<TContext> application) where TContext : notnull
	{
		Exception error = null;
		Http2ErrorCode errorCode = Http2ErrorCode.NO_ERROR;
		ConnectionEndReason reason = ConnectionEndReason.Unset;
		try
		{
			_ = 6;
			try
			{
				ValidateTlsRequirements();
				TimeoutControl.InitializeHttp2(_inputFlowControl);
				TimeoutControl.SetTimeout(Limits.KeepAliveTimeout, TimeoutReason.KeepAlive);
				if (!(await TryReadPrefaceAsync()))
				{
					reason = ConnectionEndReason.TransportCompleted;
					return;
				}
				if (_isClosed == 0)
				{
					await _frameWriter.WriteSettingsAsync(_serverSettings.GetNonProtocolDefaults());
					int num = _context.ServiceContext.ServerOptions.Limits.Http2.InitialConnectionWindowSize - 65535;
					if (num > 0)
					{
						await _frameWriter.WriteWindowUpdateAsync(0, num);
					}
				}
				while (_isClosed == 0)
				{
					ReadResult result = await Input.ReadAsync();
					ReadOnlySequence<byte> buffer = result.Buffer;
					UpdateCompletedStreams();
					if (result.IsCanceled)
					{
						StreamPool.RemoveExpired(TimeProvider.GetTimestamp());
					}
					try
					{
						bool frameReceived = false;
						ReadOnlySequence<byte> framePayload;
						while (Http2FrameReader.TryReadFrame(ref buffer, _incomingFrame, _serverSettings.MaxFrameSize, out framePayload))
						{
							frameReceived = true;
							Log.Http2FrameReceived(ConnectionId, _incomingFrame);
							try
							{
								await ProcessFrameAsync(application, in framePayload);
							}
							catch (Http2StreamErrorException ex)
							{
								Log.Http2StreamError(ConnectionId, ex);
								AbortStream(_incomingFrame.StreamId, new IOException(ex.Message, ex));
								await _frameWriter.WriteRstStreamAsync(ex.StreamId, ex.ErrorCode);
							}
						}
						if (result.IsCompleted)
						{
							reason = ConnectionEndReason.TransportCompleted;
							return;
						}
						if (_keepAlive != null)
						{
							switch (_keepAlive.ProcessKeepAlive(frameReceived))
							{
							case KeepAliveState.SendPing:
								await _frameWriter.WritePingAsync(Http2PingFrameFlags.NONE, in Http2KeepAlive.PingPayload);
								break;
							case KeepAliveState.Timeout:
								throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorKeepAliveTimeout, Http2ErrorCode.INTERNAL_ERROR, ConnectionEndReason.KeepAliveTimeout);
							}
						}
					}
					finally
					{
						Input.AdvanceTo(buffer.Start, buffer.End);
						UpdateConnectionState();
					}
				}
			}
			catch (ConnectionResetException ex2)
			{
				if (_clientActiveStreamCount > 0)
				{
					Log.RequestProcessingError(ConnectionId, ex2);
					reason = ConnectionEndReason.ConnectionReset;
				}
				else
				{
					reason = ConnectionEndReason.TransportCompleted;
				}
				error = ex2;
			}
			catch (IOException ex3)
			{
				Log.RequestProcessingError(ConnectionId, ex3);
				error = ex3;
				reason = ConnectionEndReason.IOError;
			}
			catch (ConnectionAbortedException ex4)
			{
				Log.RequestProcessingError(ConnectionId, ex4);
				error = ex4;
			}
			catch (Http2ConnectionErrorException ex5)
			{
				Log.Http2ConnectionError(ConnectionId, ex5);
				error = ex5;
				errorCode = ex5.ErrorCode;
				reason = ex5.Reason;
			}
			catch (HPackDecodingException ex6)
			{
				Log.HPackDecodingError(ConnectionId, _currentHeadersStream.StreamId, ex6);
				error = ex6;
				errorCode = Http2ErrorCode.COMPRESSION_ERROR;
				reason = ConnectionEndReason.ErrorReadingHeaders;
			}
			catch (Exception ex7)
			{
				Log.LogWarning(0, ex7, CoreStrings.RequestProcessingEndError);
				error = ex7;
				errorCode = Http2ErrorCode.INTERNAL_ERROR;
				reason = ConnectionEndReason.OtherError;
			}
		}
		finally
		{
			ConnectionAbortedException connectionError = (error as ConnectionAbortedException) ?? new ConnectionAbortedException(CoreStrings.Http2ConnectionFaulted, error);
			try
			{
				int num2;
				_ = num2 - 7;
				_ = 1;
				try
				{
					if (TryClose())
					{
						SetConnectionErrorCode(reason, errorCode);
						await _frameWriter.WriteGoAwayAsync(_highestOpenedStreamId, errorCode);
					}
					_inputFlowControl.StopWindowUpdates();
					foreach (Http2Stream value in _streams.Values)
					{
						value.Abort(new IOException(CoreStrings.Http2StreamAborted, connectionError));
					}
					if (!IsEnhanceYourCalmLimitEnabled || !(error is Http2ConnectionErrorException))
					{
						while (_serverActiveStreamCount > 0)
						{
							await _streamCompletionAwaitable;
							UpdateCompletedStreams();
						}
					}
					Http2Stream result2;
					while (StreamPool.TryPop(out result2))
					{
						result2.Dispose();
					}
					TimeoutControl.CancelTimeout();
					TimeoutControl.StartDrainTimeout(Limits.MinResponseDataRate, Limits.MaxResponseBufferSize);
					_frameWriter.Complete();
				}
				catch
				{
					_frameWriter.Abort(connectionError);
					throw;
				}
			}
			finally
			{
				Input.Complete();
				_context.Transport.Input.CancelPendingRead();
				await _inputTask;
				await _frameWriter.ShutdownAsync();
			}
		}
	}

	private void ValidateTlsRequirements()
	{
		ITlsHandshakeFeature tlsHandshakeFeature = ConnectionFeatures.Get<ITlsHandshakeFeature>();
		if (tlsHandshakeFeature == null || tlsHandshakeFeature.Protocol >= SslProtocols.Tls12)
		{
			return;
		}
		throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorMinTlsVersion(tlsHandshakeFeature.Protocol), Http2ErrorCode.INADEQUATE_SECURITY, ConnectionEndReason.InsufficientTlsVersion);
	}

	private async Task<bool> TryReadPrefaceAsync()
	{
		ReadPrefaceState state = ReadPrefaceState.All;
		if (ConnectionFeatures.Get<ITlsHandshakeFeature>() != null)
		{
			state ^= ReadPrefaceState.Http1x;
		}
		while (_isClosed == 0)
		{
			ReadResult readResult = await Input.ReadAsync();
			ReadOnlySequence<byte> buffer = readResult.Buffer;
			SequencePosition consumed = buffer.Start;
			SequencePosition examined = buffer.End;
			try
			{
				if (!buffer.IsEmpty)
				{
					if (state.HasFlag(ReadPrefaceState.Preface) && buffer.Length >= ClientPreface.Length)
					{
						if (IsPreface(in buffer, out consumed, out examined))
						{
							return true;
						}
						state ^= ReadPrefaceState.Preface;
					}
					if (state.HasFlag(ReadPrefaceState.Http1x) && ParseHttp1x(buffer, out var httpVersion))
					{
						if (httpVersion == HttpVersion.Http10 || httpVersion == HttpVersion.Http11)
						{
							Log.PossibleInvalidHttpVersionDetected(ConnectionId, HttpVersion.Http2, httpVersion);
							byte[] array = InvalidHttp1xErrorResponseBytes ?? (InvalidHttp1xErrorResponseBytes = Encoding.ASCII.GetBytes("HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Type: text/plain\r\nContent-Length: 56\r\n\r\nAn HTTP/1.x request was sent to an HTTP/2 only endpoint."));
							await _context.Transport.Output.WriteAsync(array);
							if (TryClose())
							{
								SetConnectionErrorCode(ConnectionEndReason.InvalidHttpVersion, Http2ErrorCode.PROTOCOL_ERROR);
							}
							return false;
						}
						state ^= ReadPrefaceState.Http1x;
					}
					if (state == ReadPrefaceState.None)
					{
						throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorInvalidPreface, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidHandshake);
					}
				}
				if (readResult.IsCompleted)
				{
					return false;
				}
			}
			finally
			{
				Input.AdvanceTo(consumed, examined);
				UpdateConnectionState();
			}
		}
		return false;
	}

	private bool ParseHttp1x(ReadOnlySequence<byte> buffer, out HttpVersion httpVersion)
	{
		httpVersion = HttpVersion.Unknown;
		SequenceReader<byte> sequenceReader = new SequenceReader<byte>((buffer.Length > Limits.MaxRequestLineSize) ? buffer.Slice(0, Limits.MaxRequestLineSize) : buffer);
		if (sequenceReader.TryReadTo(out ReadOnlySpan<byte> span, (byte)10, true))
		{
			if (span.Length > 10 && span[span.Length - 1] == 13)
			{
				httpVersion = span.Slice(span.Length - 9, 8).GetKnownVersion();
			}
			return true;
		}
		if (buffer.Length > Limits.MaxRequestLineSize)
		{
			return true;
		}
		return false;
	}

	private static bool IsPreface(in ReadOnlySequence<byte> buffer, out SequencePosition consumed, out SequencePosition examined)
	{
		consumed = buffer.Start;
		examined = buffer.End;
		ReadOnlySequence<byte> buffer2 = buffer.Slice(0, ClientPreface.Length);
		if (!buffer2.ToSpan().SequenceEqual(ClientPreface))
		{
			return false;
		}
		consumed = (examined = buffer2.End);
		return true;
	}

	private Task ProcessFrameAsync<TContext>(IHttpApplication<TContext> application, in ReadOnlySequence<byte> payload)
	{
		if (_incomingFrame.StreamId != 0 && (_incomingFrame.StreamId & 1) == 0)
		{
			throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamIdEven(_incomingFrame.Type, _incomingFrame.StreamId), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidStreamId);
		}
		return _incomingFrame.Type switch
		{
			Http2FrameType.DATA => ProcessDataFrameAsync(in payload), 
			Http2FrameType.HEADERS => ProcessHeadersFrameAsync(application, in payload), 
			Http2FrameType.PRIORITY => ProcessPriorityFrameAsync(), 
			Http2FrameType.RST_STREAM => ProcessRstStreamFrameAsync(), 
			Http2FrameType.SETTINGS => ProcessSettingsFrameAsync(in payload), 
			Http2FrameType.PUSH_PROMISE => throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorPushPromiseReceived, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.UnexpectedFrame), 
			Http2FrameType.PING => ProcessPingFrameAsync(in payload), 
			Http2FrameType.GOAWAY => ProcessGoAwayFrameAsync(), 
			Http2FrameType.WINDOW_UPDATE => ProcessWindowUpdateFrameAsync(), 
			Http2FrameType.CONTINUATION => ProcessContinuationFrameAsync(in payload), 
			_ => ProcessUnknownFrameAsync(), 
		};
	}

	private Task ProcessDataFrameAsync(in ReadOnlySequence<byte> payload)
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_incomingFrame.StreamId == 0)
		{
			throw CreateStreamIdZeroException();
		}
		if (_incomingFrame.DataHasPadding && _incomingFrame.DataPadLength >= _incomingFrame.PayloadLength)
		{
			throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorPaddingTooLong(_incomingFrame.Type), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidDataPadding);
		}
		ThrowIfIncomingFrameSentToIdleStream();
		if (_streams.TryGetValue(_incomingFrame.StreamId, out Http2Stream value))
		{
			if (value.RstStreamReceived)
			{
				throw CreateReceivedFrameStreamAbortedException(value);
			}
			if (value.EndStreamReceived)
			{
				throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamHalfClosedRemote(_incomingFrame.Type, value.StreamId), Http2ErrorCode.STREAM_CLOSED, ConnectionEndReason.FrameAfterStreamClose);
			}
			return value.OnDataAsync(_incomingFrame, in payload);
		}
		throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamClosed(_incomingFrame.Type, _incomingFrame.StreamId), Http2ErrorCode.STREAM_CLOSED, ConnectionEndReason.UnknownStream);
	}

	private Http2ConnectionErrorException CreateReceivedFrameStreamAbortedException(Http2Stream stream)
	{
		return new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamAborted(_incomingFrame.Type, stream.StreamId), Http2ErrorCode.STREAM_CLOSED, ConnectionEndReason.FrameAfterStreamClose);
	}

	private Http2ConnectionErrorException CreateStreamIdZeroException()
	{
		return new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamIdZero(_incomingFrame.Type), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidStreamId);
	}

	private Http2ConnectionErrorException CreateStreamIdNotZeroException()
	{
		return new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamIdNotZero(_incomingFrame.Type), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidStreamId);
	}

	private Http2ConnectionErrorException CreateHeadersInterleavedException()
	{
		return new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorHeadersInterleaved(_incomingFrame.Type, _incomingFrame.StreamId, _currentHeadersStream.StreamId), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.UnexpectedFrame);
	}

	private Http2ConnectionErrorException CreateUnexpectedFrameLengthException(int expectedLength)
	{
		return new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorUnexpectedFrameLength(_incomingFrame.Type, expectedLength), Http2ErrorCode.FRAME_SIZE_ERROR, ConnectionEndReason.InvalidFrameLength);
	}

	private Task ProcessHeadersFrameAsync<TContext>(IHttpApplication<TContext> application, in ReadOnlySequence<byte> payload)
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_incomingFrame.StreamId == 0)
		{
			throw CreateStreamIdZeroException();
		}
		if (_incomingFrame.HeadersHasPadding && _incomingFrame.HeadersPadLength >= _incomingFrame.PayloadLength - 1)
		{
			throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorPaddingTooLong(_incomingFrame.Type), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidDataPadding);
		}
		if (_incomingFrame.HeadersHasPriority && _incomingFrame.HeadersStreamDependency == _incomingFrame.StreamId)
		{
			throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamSelfDependency(_incomingFrame.Type, _incomingFrame.StreamId), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.StreamSelfDependency);
		}
		if (_streams.TryGetValue(_incomingFrame.StreamId, out Http2Stream value))
		{
			if (value.RstStreamReceived)
			{
				throw CreateReceivedFrameStreamAbortedException(value);
			}
			if (value.EndStreamReceived)
			{
				throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamHalfClosedRemote(_incomingFrame.Type, value.StreamId), Http2ErrorCode.STREAM_CLOSED, ConnectionEndReason.FrameAfterStreamClose);
			}
			if (!_incomingFrame.HeadersEndStream)
			{
				throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorHeadersWithTrailersNoEndStream, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.MissingStreamEnd);
			}
			_currentHeadersStream = value;
			_requestHeaderParsingState = RequestHeaderParsingState.Trailers;
			ReadOnlySequence<byte> payload2 = payload.Slice(0, _incomingFrame.HeadersPayloadLength);
			return DecodeTrailersAsync(_incomingFrame.HeadersEndHeaders, in payload2);
		}
		if (_incomingFrame.StreamId <= _highestOpenedStreamId)
		{
			throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamClosed(_incomingFrame.Type, _incomingFrame.StreamId), Http2ErrorCode.STREAM_CLOSED, ConnectionEndReason.InvalidStreamId);
		}
		if (TimeoutControl.TimerReason != TimeoutReason.None)
		{
			TimeoutControl.CancelTimeout();
		}
		if (!_incomingFrame.HeadersEndHeaders)
		{
			TimeoutControl.SetTimeout(Limits.RequestHeadersTimeout, TimeoutReason.RequestHeaders);
		}
		_currentHeadersStream = GetStream(application);
		_headerFlags = _incomingFrame.HeadersFlags;
		ReadOnlySequence<byte> payload3 = payload.Slice(0, _incomingFrame.HeadersPayloadLength);
		return DecodeHeadersAsync(_incomingFrame.HeadersEndHeaders, in payload3);
	}

	private Http2Stream GetStream<TContext>(IHttpApplication<TContext> application)
	{
		if (StreamPool.TryPop(out Http2Stream result))
		{
			result.InitializeWithExistingContext(_incomingFrame.StreamId);
			return result;
		}
		return new Http2Stream<TContext>(application, CreateHttp2StreamContext());
	}

	private Http2StreamContext CreateHttp2StreamContext()
	{
		return new Http2StreamContext(ConnectionId, HttpProtocols.None, _context.AltSvcHeader, _context.ConnectionContext, _context.ServiceContext, _context.ConnectionFeatures, _context.MemoryPool, _context.LocalEndPoint, _context.RemoteEndPoint, _incomingFrame.StreamId, _streamLifetimeHandler, _clientSettings, _serverSettings, _frameWriter, _inputFlowControl, _metricsContext)
		{
			TimeoutControl = _context.TimeoutControl,
			InitialExecutionContext = _context.InitialExecutionContext
		};
	}

	private Task ProcessPriorityFrameAsync()
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_incomingFrame.StreamId == 0)
		{
			throw CreateStreamIdZeroException();
		}
		if (_incomingFrame.PriorityStreamDependency == _incomingFrame.StreamId)
		{
			throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamSelfDependency(_incomingFrame.Type, _incomingFrame.StreamId), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.StreamSelfDependency);
		}
		if (_incomingFrame.PayloadLength != 5)
		{
			throw CreateUnexpectedFrameLengthException(5);
		}
		return Task.CompletedTask;
	}

	private Task ProcessRstStreamFrameAsync()
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_incomingFrame.StreamId == 0)
		{
			throw CreateStreamIdZeroException();
		}
		if (_incomingFrame.PayloadLength != 4)
		{
			throw CreateUnexpectedFrameLengthException(4);
		}
		ThrowIfIncomingFrameSentToIdleStream();
		if (_streams.TryGetValue(_incomingFrame.StreamId, out Http2Stream value))
		{
			if (value.RstStreamReceived)
			{
				return Task.CompletedTask;
			}
			value.AbortRstStreamReceived();
		}
		return Task.CompletedTask;
	}

	private Task ProcessSettingsFrameAsync(in ReadOnlySequence<byte> payload)
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_incomingFrame.StreamId != 0)
		{
			throw CreateStreamIdNotZeroException();
		}
		if (_incomingFrame.SettingsAck)
		{
			if (_incomingFrame.PayloadLength != 0)
			{
				throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorSettingsAckLengthNotZero, Http2ErrorCode.FRAME_SIZE_ERROR, ConnectionEndReason.InvalidFrameLength);
			}
			return Task.CompletedTask;
		}
		if (_incomingFrame.PayloadLength % 6 != 0)
		{
			throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorSettingsLengthNotMultipleOfSix, Http2ErrorCode.FRAME_SIZE_ERROR, ConnectionEndReason.InvalidFrameLength);
		}
		try
		{
			int initialWindowSize = (int)_clientSettings.InitialWindowSize;
			uint maxFrameSize = _clientSettings.MaxFrameSize;
			_clientSettings.Update(Http2FrameReader.ReadSettings(in payload));
			ValueTask<FlushResult> valueTask = _frameWriter.WriteSettingsAckAsync();
			if (_clientSettings.MaxFrameSize != maxFrameSize)
			{
				_frameWriter.UpdateMaxFrameSize((int)Math.Min(_clientSettings.MaxFrameSize, _serverSettings.MaxFrameSize));
			}
			int num = (int)_clientSettings.InitialWindowSize - initialWindowSize;
			if (num != 0)
			{
				foreach (Http2Stream value in _streams.Values)
				{
					if (!value.TryUpdateOutputWindow(num))
					{
						throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorInitialWindowSizeInvalid, Http2ErrorCode.FLOW_CONTROL_ERROR, ConnectionEndReason.InvalidSettings);
					}
				}
			}
			_frameWriter.UpdateMaxHeaderTableSize(Math.Min(_clientSettings.HeaderTableSize, (uint)Limits.Http2.HeaderTableSize));
			return valueTask.GetAsTask();
		}
		catch (Http2SettingsParameterOutOfRangeException ex)
		{
			throw new Http2ConnectionErrorException(errorCode: (ex.Parameter != Http2SettingsParameter.SETTINGS_INITIAL_WINDOW_SIZE) ? Http2ErrorCode.PROTOCOL_ERROR : Http2ErrorCode.FLOW_CONTROL_ERROR, message: CoreStrings.FormatHttp2ErrorSettingsParameterOutOfRange(ex.Parameter), reason: ConnectionEndReason.InvalidSettings);
		}
	}

	private Task ProcessPingFrameAsync(in ReadOnlySequence<byte> payload)
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_incomingFrame.StreamId != 0)
		{
			throw CreateStreamIdNotZeroException();
		}
		if (_incomingFrame.PayloadLength != 8)
		{
			throw CreateUnexpectedFrameLengthException(8);
		}
		if (TimeoutControl.TimerReason == TimeoutReason.KeepAlive)
		{
			TimeoutControl.ResetTimeout(Limits.KeepAliveTimeout, TimeoutReason.KeepAlive);
		}
		if (_incomingFrame.PingAck)
		{
			return Task.CompletedTask;
		}
		return _frameWriter.WritePingAsync(Http2PingFrameFlags.ACK, in payload).GetAsTask();
	}

	private Task ProcessGoAwayFrameAsync()
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_incomingFrame.StreamId != 0)
		{
			throw CreateStreamIdNotZeroException();
		}
		StopProcessingNextRequest(serverInitiated: false, ConnectionEndReason.ClientGoAway);
		_context.ConnectionFeatures.Get<IConnectionLifetimeNotificationFeature>()?.RequestClose();
		return Task.CompletedTask;
	}

	private Task ProcessWindowUpdateFrameAsync()
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_incomingFrame.PayloadLength != 4)
		{
			throw CreateUnexpectedFrameLengthException(4);
		}
		ThrowIfIncomingFrameSentToIdleStream();
		if (_incomingFrame.WindowUpdateSizeIncrement == 0)
		{
			throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorWindowUpdateIncrementZero, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidWindowUpdateSize);
		}
		Http2Stream value;
		if (_incomingFrame.StreamId == 0)
		{
			if (!_frameWriter.TryUpdateConnectionWindow(_incomingFrame.WindowUpdateSizeIncrement))
			{
				throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorWindowUpdateSizeInvalid, Http2ErrorCode.FLOW_CONTROL_ERROR, ConnectionEndReason.InvalidWindowUpdateSize);
			}
		}
		else if (_streams.TryGetValue(_incomingFrame.StreamId, out value))
		{
			if (value.RstStreamReceived)
			{
				throw new Http2StreamErrorException(_incomingFrame.StreamId, CoreStrings.Http2StreamAborted, Http2ErrorCode.STREAM_CLOSED);
			}
			if (!value.TryUpdateOutputWindow(_incomingFrame.WindowUpdateSizeIncrement))
			{
				throw new Http2StreamErrorException(_incomingFrame.StreamId, CoreStrings.Http2ErrorWindowUpdateSizeInvalid, Http2ErrorCode.FLOW_CONTROL_ERROR);
			}
		}
		return Task.CompletedTask;
	}

	private Task ProcessContinuationFrameAsync(in ReadOnlySequence<byte> payload)
	{
		if (_currentHeadersStream == null)
		{
			throw new Http2ConnectionErrorException(CoreStrings.Http2ErrorContinuationWithNoHeaders, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.UnexpectedFrame);
		}
		if (_incomingFrame.StreamId != _currentHeadersStream.StreamId)
		{
			throw CreateHeadersInterleavedException();
		}
		if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers)
		{
			return DecodeTrailersAsync(_incomingFrame.ContinuationEndHeaders, in payload);
		}
		if (_incomingFrame.HeadersEndHeaders)
		{
			TimeoutControl.CancelTimeout();
		}
		return DecodeHeadersAsync(_incomingFrame.ContinuationEndHeaders, in payload);
	}

	private Task ProcessUnknownFrameAsync()
	{
		if (_currentHeadersStream != null)
		{
			throw CreateHeadersInterleavedException();
		}
		return Task.CompletedTask;
	}

	private Task DecodeHeadersAsync(bool endHeaders, in ReadOnlySequence<byte> payload)
	{
		try
		{
			_highestOpenedStreamId = _currentHeadersStream.StreamId;
			_hpackDecoder.Decode(in payload, endHeaders, this);
			if (endHeaders)
			{
				_currentHeadersStream.OnHeadersComplete();
				StartStream();
				ResetRequestHeaderParsingState();
			}
		}
		catch (Http2StreamErrorException)
		{
			_currentHeadersStream.Dispose();
			ResetRequestHeaderParsingState();
			throw;
		}
		return Task.CompletedTask;
	}

	private Task DecodeTrailersAsync(bool endHeaders, in ReadOnlySequence<byte> payload)
	{
		_hpackDecoder.Decode(in payload, endHeaders, this);
		if (endHeaders)
		{
			_currentHeadersStream.OnEndStreamReceived();
			ResetRequestHeaderParsingState();
		}
		return Task.CompletedTask;
	}

	private void StartStream()
	{
		_streams[_incomingFrame.StreamId] = _currentHeadersStream;
		IncrementActiveClientStreamCount();
		_serverActiveStreamCount++;
		try
		{
			_currentHeadersStream.TotalParsedHeaderSize = _totalParsedHeaderSize;
			_currentHeadersStream.InputRemaining = _currentHeadersStream.RequestHeaders.ContentLength;
			if ((_headerFlags & Http2HeadersFrameFlags.END_STREAM) == Http2HeadersFrameFlags.END_STREAM)
			{
				_currentHeadersStream.OnEndStreamReceived();
			}
			if (!_isMethodConnect && (_parsedPseudoHeaderFields & (PseudoHeaderFields.Method | PseudoHeaderFields.Path | PseudoHeaderFields.Scheme)) != (PseudoHeaderFields.Method | PseudoHeaderFields.Path | PseudoHeaderFields.Scheme))
			{
				throw new Http2StreamErrorException(_currentHeadersStream.StreamId, CoreStrings.HttpErrorMissingMandatoryPseudoHeaderFields, Http2ErrorCode.PROTOCOL_ERROR);
			}
			if (_clientActiveStreamCount == _serverSettings.MaxConcurrentStreams)
			{
				Log.Http2MaxConcurrentStreamsReached(_context.ConnectionId);
			}
			else if (_clientActiveStreamCount > _serverSettings.MaxConcurrentStreams)
			{
				throw new Http2StreamErrorException(_currentHeadersStream.StreamId, CoreStrings.Http2ErrorMaxStreams, Http2ErrorCode.REFUSED_STREAM);
			}
			if (_streams.Count > MaxTrackedStreams || SendEnhanceYourCalmOnStartStream)
			{
				if (IsEnhanceYourCalmLimitEnabled && Interlocked.Increment(ref _enhanceYourCalmCount) > 5 * EnhanceYourCalmMaximumCount)
				{
					Log.Http2TooManyEnhanceYourCalms(_context.ConnectionId, EnhanceYourCalmMaximumCount);
					Abort(new ConnectionAbortedException(CoreStrings.Http2ConnectionFaulted), Http2ErrorCode.ENHANCE_YOUR_CALM, ConnectionEndReason.StreamResetLimitExceeded);
					throw new Http2ConnectionErrorException(CoreStrings.Http2ConnectionFaulted, Http2ErrorCode.ENHANCE_YOUR_CALM, ConnectionEndReason.StreamResetLimitExceeded);
				}
				throw new Http2StreamErrorException(_currentHeadersStream.StreamId, CoreStrings.Http2TellClientToCalmDown, Http2ErrorCode.ENHANCE_YOUR_CALM);
			}
		}
		catch (Http2StreamErrorException)
		{
			MakeSpaceInDrainQueue();
			_currentHeadersStream.DecrementActiveClientStreamCount();
			_currentHeadersStream.CompleteStream(errored: true);
			throw;
		}
		KestrelEventSource.Log.RequestQueuedStart(_currentHeadersStream, Microsoft.AspNetCore.Http.HttpProtocol.Http2);
		_context.ServiceContext.Metrics.RequestQueuedStart(_metricsContext, "2");
		if (!_scheduleInline)
		{
			ThreadPool.UnsafeQueueUserWorkItem(_currentHeadersStream, preferLocal: false);
		}
		else
		{
			_currentHeadersStream.Execute();
		}
	}

	private void ResetRequestHeaderParsingState()
	{
		_currentHeadersStream = null;
		_requestHeaderParsingState = RequestHeaderParsingState.Ready;
		_parsedPseudoHeaderFields = PseudoHeaderFields.None;
		_headerFlags = Http2HeadersFrameFlags.NONE;
		_isMethodConnect = false;
		_totalParsedHeaderSize = 0;
	}

	private void ThrowIfIncomingFrameSentToIdleStream()
	{
		if (_incomingFrame.StreamId > _highestOpenedStreamId)
		{
			throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamIdle(_incomingFrame.Type, _incomingFrame.StreamId), Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidStreamId);
		}
	}

	private void AbortStream(int streamId, IOException error)
	{
		if (_streams.TryGetValue(streamId, out Http2Stream value))
		{
			value.DecrementActiveClientStreamCount();
			value.Abort(error);
		}
	}

	void IRequestProcessor.Tick(long timestamp)
	{
		Input.CancelPendingRead();
		if (IsEnhanceYourCalmLimitEnabled && ++_tickCount % 5 == 0)
		{
			Interlocked.Exchange(ref _enhanceYourCalmCount, 0);
		}
	}

	void IHttp2StreamLifetimeHandler.OnStreamCompleted(Http2Stream stream)
	{
		_completedStreams.Enqueue(stream);
		_streamCompletionAwaitable.Complete();
	}

	private void UpdateCompletedStreams()
	{
		Http2Stream http2Stream = null;
		long timestamp = TimeProvider.GetTimestamp();
		Http2Stream result;
		while (_completedStreams.TryDequeue(out result))
		{
			if (result == http2Stream)
			{
				_completedStreams.Enqueue(result);
				break;
			}
			if (result.DrainExpirationTimestamp == 0L)
			{
				_serverActiveStreamCount--;
				result.DrainExpirationTimestamp = TimeProvider.GetTimestamp(timestamp, Constants.RequestBodyDrainTimeout);
			}
			if (result.EndStreamReceived || result.RstStreamReceived || result.DrainExpirationTimestamp < timestamp)
			{
				if (result == _currentHeadersStream)
				{
					throw new Http2ConnectionErrorException(CoreStrings.FormatHttp2ErrorStreamClosed(_incomingFrame.Type, _incomingFrame.StreamId), Http2ErrorCode.STREAM_CLOSED, ConnectionEndReason.FrameAfterStreamClose);
				}
				RemoveStream(result);
			}
			else
			{
				if (http2Stream == null)
				{
					http2Stream = result;
				}
				_completedStreams.Enqueue(result);
			}
		}
	}

	private void RemoveStream(Http2Stream stream)
	{
		_streams.Remove(stream.StreamId);
		if (stream.CanReuse && StreamPool.Count < 100)
		{
			stream.DrainExpirationTimestamp = TimeProvider.GetTimestamp(StreamPoolExpiry);
			StreamPool.Push(stream);
		}
		else
		{
			stream.Dispose();
		}
	}

	private void MakeSpaceInDrainQueue()
	{
		uint maxTrackedStreams = MaxTrackedStreams;
		Http2Stream result;
		while (_streams.Count >= maxTrackedStreams && _completedStreams.TryDequeue(out result))
		{
			if (result.DrainExpirationTimestamp == 0L)
			{
				_serverActiveStreamCount--;
			}
			RemoveStream(result);
		}
	}

	private void UpdateConnectionState()
	{
		if (_isClosed != 0)
		{
			return;
		}
		if (_gracefulCloseInitiator != 0 && !_gracefulCloseStarted)
		{
			_gracefulCloseStarted = true;
			Log.Http2ConnectionClosing(_context.ConnectionId);
			if (_gracefulCloseInitiator == 1 && _clientActiveStreamCount > 0)
			{
				_frameWriter.WriteGoAwayAsync(int.MaxValue, Http2ErrorCode.NO_ERROR).Preserve();
			}
		}
		if (_clientActiveStreamCount != 0)
		{
			return;
		}
		if (_gracefulCloseStarted)
		{
			if (TryClose())
			{
				SetConnectionErrorCode(_gracefulCloseReason, Http2ErrorCode.NO_ERROR);
				_frameWriter.WriteGoAwayAsync(_highestOpenedStreamId, Http2ErrorCode.NO_ERROR).Preserve();
			}
		}
		else if (TimeoutControl.TimerReason == TimeoutReason.None)
		{
			TimeoutControl.SetTimeout(Limits.KeepAliveTimeout, TimeoutReason.KeepAlive);
		}
	}

	public void OnHeader(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		OnHeaderCore(HeaderType.NameAndValue, null, name, value);
	}

	public void OnDynamicIndexedHeader(int? index, ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		OnHeaderCore(HeaderType.Dynamic, index, name, value);
	}

	public void OnStaticIndexedHeader(int index)
	{
		ref readonly HeaderField reference = ref H2StaticTable.Get(index - 1);
		OnHeaderCore(HeaderType.Static, index, reference.Name, reference.Value);
	}

	public void OnStaticIndexedHeader(int index, ReadOnlySpan<byte> value)
	{
		OnHeaderCore(HeaderType.StaticAndValue, index, H2StaticTable.Get(index - 1).Name, value);
	}

	private void OnHeaderCore(HeaderType headerType, int? staticTableIndex, ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		_totalParsedHeaderSize += name.Length + value.Length;
		if (_totalParsedHeaderSize > _context.ServiceContext.ServerOptions.Limits.MaxRequestHeadersTotalSize * 2)
		{
			throw new Http2ConnectionErrorException(CoreStrings.BadRequest_HeadersExceedMaxTotalSize, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.MaxRequestHeadersTotalSizeExceeded);
		}
		try
		{
			if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers)
			{
				UpdateHeaderParsingState(value, GetPseudoHeaderField(name));
				ValidateHeaderContent(name, value);
				_currentHeadersStream.OnTrailer(name, value);
				return;
			}
			switch (headerType)
			{
			case HeaderType.Static:
				UpdateHeaderParsingState(value, GetPseudoHeaderField(staticTableIndex.GetValueOrDefault()));
				_currentHeadersStream.OnHeader(staticTableIndex.GetValueOrDefault(), indexOnly: true, name, value);
				break;
			case HeaderType.StaticAndValue:
				UpdateHeaderParsingState(value, GetPseudoHeaderField(staticTableIndex.GetValueOrDefault()));
				_currentHeadersStream.OnHeader(staticTableIndex.GetValueOrDefault(), indexOnly: false, name, value);
				break;
			case HeaderType.Dynamic:
				if (staticTableIndex.HasValue)
				{
					UpdateHeaderParsingState(value, GetPseudoHeaderField(staticTableIndex.GetValueOrDefault()));
					_currentHeadersStream.OnHeader(staticTableIndex.GetValueOrDefault(), indexOnly: false, name, value);
				}
				else
				{
					UpdateHeaderParsingState(value, GetPseudoHeaderField(name));
					_currentHeadersStream.OnHeader(name, value, checkForNewlineChars: true);
				}
				break;
			case HeaderType.NameAndValue:
				UpdateHeaderParsingState(value, GetPseudoHeaderField(name));
				ValidateHeaderContent(name, value);
				_currentHeadersStream.OnHeader(name, value, checkForNewlineChars: true);
				break;
			}
		}
		catch (BadHttpRequestException ex) when (ex.Reason == RequestRejectionReason.TooManyHeaders)
		{
			throw new Http2ConnectionErrorException(ex.Message, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.MaxRequestHeaderCountExceeded);
		}
		catch (Microsoft.AspNetCore.Http.BadHttpRequestException ex2)
		{
			throw new Http2ConnectionErrorException(ex2.Message, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
		}
		catch (InvalidOperationException)
		{
			throw new Http2ConnectionErrorException(CoreStrings.BadRequest_MalformedRequestInvalidHeaders, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
		}
	}

	public void OnHeadersComplete(bool endStream)
	{
		_currentHeadersStream.OnHeadersComplete();
	}

	private void ValidateHeaderContent(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		if (IsConnectionSpecificHeaderField(name, value))
		{
			throw new Http2ConnectionErrorException(CoreStrings.HttpErrorConnectionSpecificHeaderField, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
		}
		for (int i = 0; i < name.Length; i++)
		{
			if ((uint)(name[i] - 65) <= 25u)
			{
				if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers)
				{
					throw new Http2ConnectionErrorException(CoreStrings.HttpErrorTrailerNameUppercase, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
				}
				throw new Http2ConnectionErrorException(CoreStrings.HttpErrorHeaderNameUppercase, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
			}
		}
	}

	private void UpdateHeaderParsingState(ReadOnlySpan<byte> value, PseudoHeaderFields headerField)
	{
		if (headerField != PseudoHeaderFields.None)
		{
			if (_requestHeaderParsingState == RequestHeaderParsingState.Headers)
			{
				throw new Http2ConnectionErrorException(CoreStrings.HttpErrorPseudoHeaderFieldAfterRegularHeaders, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
			}
			if (_requestHeaderParsingState == RequestHeaderParsingState.Trailers)
			{
				throw new Http2ConnectionErrorException(CoreStrings.HttpErrorTrailersContainPseudoHeaderField, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
			}
			_requestHeaderParsingState = RequestHeaderParsingState.PseudoHeaderFields;
			switch (headerField)
			{
			case PseudoHeaderFields.Unknown:
				throw new Http2ConnectionErrorException(CoreStrings.HttpErrorUnknownPseudoHeaderField, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
			case PseudoHeaderFields.Status:
				throw new Http2ConnectionErrorException(CoreStrings.HttpErrorResponsePseudoHeaderField, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
			}
			if ((_parsedPseudoHeaderFields & headerField) == headerField)
			{
				throw new Http2ConnectionErrorException(CoreStrings.HttpErrorDuplicatePseudoHeaderField, Http2ErrorCode.PROTOCOL_ERROR, ConnectionEndReason.InvalidRequestHeaders);
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
			1 => PseudoHeaderFields.Authority, 
			2 => PseudoHeaderFields.Method, 
			3 => PseudoHeaderFields.Method, 
			4 => PseudoHeaderFields.Path, 
			5 => PseudoHeaderFields.Path, 
			6 => PseudoHeaderFields.Scheme, 
			7 => PseudoHeaderFields.Scheme, 
			8 => PseudoHeaderFields.Status, 
			9 => PseudoHeaderFields.Status, 
			10 => PseudoHeaderFields.Status, 
			11 => PseudoHeaderFields.Status, 
			12 => PseudoHeaderFields.Status, 
			13 => PseudoHeaderFields.Status, 
			14 => PseudoHeaderFields.Status, 
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

	private bool TryClose()
	{
		if (Interlocked.Exchange(ref _isClosed, 1) == 0)
		{
			Log.Http2ConnectionClosed(_context.ConnectionId, _highestOpenedStreamId);
			return true;
		}
		return false;
	}

	public void IncrementActiveClientStreamCount()
	{
		Interlocked.Increment(ref _clientActiveStreamCount);
	}

	public void DecrementActiveClientStreamCount()
	{
		Interlocked.Decrement(ref _clientActiveStreamCount);
	}

	private PipeOptions GetInputPipeOptions()
	{
		return new PipeOptions(_context.MemoryPool, _context.ServiceContext.Scheduler, PipeScheduler.Inline, 1L, 1L, _context.MemoryPool.GetMinimumSegmentSize(), useSynchronizationContext: false);
	}

	private async Task CopyPipeAsync(PipeReader reader, PipeWriter writer)
	{
		Exception error = null;
		try
		{
			_ = 1;
			try
			{
				FlushResult flushResult;
				do
				{
					ReadResult readResult = await reader.ReadAsync();
					if ((!readResult.IsCompleted || readResult.Buffer.Length != 0L) && !readResult.IsCanceled)
					{
						Memory<byte> memory = writer.GetMemory(_minAllocBufferSize);
						int num = (int)Math.Min(memory.Length, readResult.Buffer.Length);
						ReadOnlySequence<byte> bufferSlice = readResult.Buffer.Slice(0, num);
						bufferSlice.CopyTo(memory.Span);
						writer.Advance(num);
						flushResult = await writer.FlushAsync();
						reader.AdvanceTo(bufferSlice.End);
						continue;
					}
					break;
				}
				while (!flushResult.IsCompleted && !flushResult.IsCanceled);
			}
			catch (Exception ex)
			{
				error = ex;
			}
		}
		finally
		{
			await reader.CompleteAsync(error);
			await writer.CompleteAsync(error);
		}
	}
}
