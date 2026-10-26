using System;
using System.Buffers;
using System.Collections.Generic;
using System.IO.Pipelines;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Connections;
using Microsoft.AspNetCore.Connections.Features;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Internal;
using Microsoft.AspNetCore.Server.Kestrel.Core.Features;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;

internal class Http1Connection : HttpProtocol, IRequestProcessor, IHttpOutputAborter, IHttpMinRequestBodyDataRateFeature, IHttpMinResponseDataRateFeature, IPersistentStateFeature
{
	private const byte ByteCR = 13;

	private const byte ByteLF = 10;

	private const byte ByteAsterisk = 42;

	private const byte ByteForwardSlash = 47;

	private const string Asterisk = "*";

	private const string ForwardSlash = "/";

	private readonly HttpConnectionContext _context;

	private readonly IHttpParser<Http1ParsingHandler> _parser;

	private readonly Http1OutputProducer _http1Output;

	private volatile bool _requestTimedOut;

	private uint _requestCount;

	private HttpRequestTarget _requestTargetForm = HttpRequestTarget.Unknown;

	private Uri _absoluteRequestTarget;

	private string _parsedPath;

	private string _parsedQueryString;

	private string _parsedRawTarget;

	private Uri _parsedAbsoluteRequestTarget;

	private long _remainingRequestHeadersBytesAllowed;

	private bool _http2PrefaceDetected;

	private IDictionary<object, object> _persistentState;

	internal static ReadOnlySpan<byte> Http2GoAwayHttp11RequiredBytes => new byte[17]
	{
		0, 0, 8, 7, 0, 0, 0, 0, 0, 0,
		0, 0, 0, 0, 0, 0, 13
	};

	public ConnectionMetricsContext MetricsContext => _context.MetricsContext;

	public PipeReader Input { get; }

	public bool RequestTimedOut => _requestTimedOut;

	public MinDataRate? MinResponseDataRate { get; set; }

	public MemoryPool<byte> MemoryPool { get; }

	MinDataRate? IHttpMinRequestBodyDataRateFeature.MinDataRate
	{
		get
		{
			return MinRequestBodyDataRate;
		}
		set
		{
			MinRequestBodyDataRate = value;
		}
	}

	MinDataRate? IHttpMinResponseDataRateFeature.MinDataRate
	{
		get
		{
			return MinResponseDataRate;
		}
		set
		{
			MinResponseDataRate = value;
		}
	}

	IDictionary<object, object?> IPersistentStateFeature.State => _persistentState ?? (_persistentState = new ConnectionItems());

	public Http1Connection(HttpConnectionContext context)
	{
		Initialize(context);
		_context = context;
		_parser = ServiceContext.HttpParser;
		_http1Output = new Http1OutputProducer(_context.Transport.Output, _context.ConnectionId, _context.ConnectionContext, _context.MemoryPool, _context.ServiceContext.Log, _context.TimeoutControl, this, MetricsContext, this);
		Input = _context.Transport.Input;
		Output = _http1Output;
		MemoryPool = _context.MemoryPool;
	}

	protected override void OnRequestProcessingEnded()
	{
		if (IsUpgraded)
		{
			KestrelEventSource.Log.RequestUpgradedStop(this);
			ServiceContext.Metrics.RequestUpgradedStop(MetricsContext);
			ServiceContext.ConnectionManager.UpgradedConnectionCount.ReleaseOne();
		}
		TimeoutControl.StartDrainTimeout(MinResponseDataRate, ServerOptions.Limits.MaxResponseBufferSize);
		Reset();
		_http1Output.Dispose();
	}

	void IRequestProcessor.OnInputOrOutputCompleted()
	{
		_http1Output.Abort(ServerOptions.FinOnError ? new ConnectionAbortedException(CoreStrings.ConnectionAbortedByClient) : null, ConnectionEndReason.TransportCompleted);
		CancelRequestAbortedToken();
	}

	void IHttpOutputAborter.OnInputOrOutputCompleted()
	{
		_http1Output.Abort(new ConnectionAbortedException(CoreStrings.ConnectionAbortedByClient), ConnectionEndReason.TransportCompleted);
		CancelRequestAbortedToken();
	}

	public void Abort(ConnectionAbortedException abortReason, ConnectionEndReason reason)
	{
		_http1Output.Abort(abortReason, reason);
		CancelRequestAbortedToken();
		PoisonBody(abortReason);
	}

	protected override void ApplicationAbort()
	{
		Log.ApplicationAbortedConnection(ConnectionId, TraceIdentifier);
		Abort(new ConnectionAbortedException(CoreStrings.ConnectionAbortedByApplication), ConnectionEndReason.AbortedByApp);
	}

	public void StopProcessingNextRequest(ConnectionEndReason reason)
	{
		DisableKeepAlive(reason);
		Input.CancelPendingRead();
	}

	internal override void DisableKeepAlive(ConnectionEndReason reason)
	{
		KestrelMetrics.AddConnectionEndReason(MetricsContext, reason);
		_keepAlive = false;
	}

	public void SendTimeoutResponse()
	{
		_requestTimedOut = true;
		Input.CancelPendingRead();
	}

	public void HandleRequestHeadersTimeout()
	{
		KestrelMetrics.AddConnectionEndReason(MetricsContext, ConnectionEndReason.RequestHeadersTimeout);
		SendTimeoutResponse();
	}

	public void HandleReadDataRateTimeout()
	{
		KestrelMetrics.AddConnectionEndReason(MetricsContext, ConnectionEndReason.MinRequestBodyDataRate);
		Log.RequestBodyMinimumDataRateNotSatisfied(ConnectionId, TraceIdentifier, MinRequestBodyDataRate.BytesPerSecond);
		SendTimeoutResponse();
	}

	public bool ParseRequest(ref SequenceReader<byte> reader)
	{
		switch (_requestProcessingStatus)
		{
		case RequestProcessingStatus.RequestPending:
		{
			if (reader.TryPeek(out var value) && (value == 13 || value == 10))
			{
				reader.AdvancePastAny(13, 10);
			}
			if (reader.End)
			{
				break;
			}
			TimeoutControl.ResetTimeout(ServerOptions.Limits.RequestHeadersTimeout, TimeoutReason.RequestHeaders);
			_requestProcessingStatus = RequestProcessingStatus.ParsingRequestLine;
			goto case RequestProcessingStatus.ParsingRequestLine;
		}
		case RequestProcessingStatus.ParsingRequestLine:
			if (!TakeStartLine(ref reader))
			{
				break;
			}
			_requestProcessingStatus = RequestProcessingStatus.ParsingHeaders;
			goto case RequestProcessingStatus.ParsingHeaders;
		case RequestProcessingStatus.ParsingHeaders:
			if (TakeMessageHeaders(ref reader, trailers: false))
			{
				_requestProcessingStatus = RequestProcessingStatus.AppStarted;
				return true;
			}
			break;
		}
		return false;
	}

	public bool TakeStartLine(ref SequenceReader<byte> reader)
	{
		if (reader.Remaining >= ServerOptions.Limits.MaxRequestLineSize)
		{
			return TrimAndTakeStartLine(ref reader);
		}
		return _parser.ParseRequestLine(new Http1ParsingHandler(this), ref reader);
		bool TrimAndTakeStartLine(ref SequenceReader<byte> reference)
		{
			ReadOnlySequence<byte> sequence = reference.Sequence.Slice(reference.Position, ServerOptions.Limits.MaxRequestLineSize);
			SequenceReader<byte> reader2 = new SequenceReader<byte>(sequence);
			if (!_parser.ParseRequestLine(new Http1ParsingHandler(this), ref reader2))
			{
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.RequestLineTooLong);
			}
			reference.Advance(reader2.Consumed);
			return true;
		}
	}

	public bool TakeMessageHeaders(ref SequenceReader<byte> reader, bool trailers)
	{
		if (reader.Remaining > _remainingRequestHeadersBytesAllowed)
		{
			return TrimAndTakeMessageHeaders(ref reader, trailers);
		}
		long consumed = reader.Consumed;
		try
		{
			bool flag = _parser.ParseHeaders(new Http1ParsingHandler(this, trailers), ref reader);
			if (flag)
			{
				TimeoutControl.CancelTimeout();
			}
			return flag;
		}
		finally
		{
			_remainingRequestHeadersBytesAllowed -= reader.Consumed - consumed;
		}
		bool TrimAndTakeMessageHeaders(ref SequenceReader<byte> reference, bool trailers2)
		{
			ReadOnlySequence<byte> sequence = reference.Sequence.Slice(reference.Position, _remainingRequestHeadersBytesAllowed);
			SequenceReader<byte> reader2 = new SequenceReader<byte>(sequence);
			try
			{
				if (!_parser.ParseHeaders(new Http1ParsingHandler(this, trailers2), ref reader2))
				{
					KestrelBadHttpRequestException.Throw(RequestRejectionReason.HeadersExceedMaxTotalSize);
				}
				TimeoutControl.CancelTimeout();
				reference.Advance(reader2.Consumed);
				return true;
			}
			finally
			{
				_remainingRequestHeadersBytesAllowed -= reader2.Consumed;
			}
		}
	}

	public void OnStartLine(HttpVersionAndMethod versionAndMethod, TargetOffsetPathLength targetPath, Span<byte> startLine)
	{
		int offset = targetPath.Offset;
		int num = offset;
		Span<byte> target = startLine.Slice(num, startLine.Length - num);
		HttpMethod method = versionAndMethod.Method;
		byte b = target[0];
		if (b == 47)
		{
			OnOriginFormTarget(targetPath, target);
		}
		else if (b == 42 && target.Length == 1)
		{
			OnAsteriskFormTarget(method);
		}
		else
		{
			num = offset;
			if (startLine.Slice(num, startLine.Length - num).GetKnownHttpScheme(out var _))
			{
				OnAbsoluteFormTarget(targetPath, target);
			}
			else
			{
				OnAuthorityFormTarget(method, target);
			}
		}
		Method = method;
		if (method == HttpMethod.Custom)
		{
			_methodText = startLine.Slice(0, versionAndMethod.MethodEnd).GetAsciiString();
		}
		_httpVersion = versionAndMethod.Version;
	}

	private void OnOriginFormTarget(TargetOffsetPathLength targetPath, Span<byte> target)
	{
		_requestTargetForm = HttpRequestTarget.OriginForm;
		if (target.Length == 1)
		{
			RawTarget = "/";
			Path = "/";
			QueryString = string.Empty;
			_parsedRawTarget = (_parsedPath = (_parsedQueryString = null));
			_parsedAbsoluteRequestTarget = null;
			return;
		}
		string parsedRawTarget = _parsedRawTarget;
		if (ServerOptions.DisableStringReuse || parsedRawTarget == null || parsedRawTarget.Length != target.Length || !StringUtilities.BytesOrdinalEqualsStringAndAscii(parsedRawTarget, target))
		{
			ParseTarget(targetPath, target);
		}
		else
		{
			RawTarget = parsedRawTarget;
			Path = _parsedPath;
			QueryString = _parsedQueryString;
		}
		_parsedAbsoluteRequestTarget = null;
	}

	private void ParseTarget(TargetOffsetPathLength targetPath, Span<byte> target)
	{
		try
		{
			RawTarget = (_parsedRawTarget = target.GetAsciiString());
			int queryLength = 0;
			if (target.Length == targetPath.Length)
			{
				if ((object)_parsedQueryString == string.Empty)
				{
					QueryString = _parsedQueryString;
				}
				else
				{
					QueryString = string.Empty;
					_parsedQueryString = string.Empty;
				}
			}
			else
			{
				queryLength = ParseQuery(targetPath, target);
			}
			int length = targetPath.Length;
			if (length == 1)
			{
				Path = (_parsedPath = "/");
				return;
			}
			Span<byte> path = target.Slice(0, length);
			Path = (_parsedPath = PathDecoder.DecodePath(path, targetPath.IsEncoded, RawTarget, queryLength));
		}
		catch (InvalidOperationException)
		{
			ThrowRequestTargetRejected(target);
		}
	}

	private int ParseQuery(TargetOffsetPathLength targetPath, Span<byte> target)
	{
		string parsedQueryString = _parsedQueryString;
		int length = targetPath.Length;
		Span<byte> span = target.Slice(length, target.Length - length);
		int length2 = span.Length;
		if (ServerOptions.DisableStringReuse || parsedQueryString == null || parsedQueryString.Length != length2 || !StringUtilities.BytesOrdinalEqualsStringAndAscii(parsedQueryString, span))
		{
			QueryString = (_parsedQueryString = span.GetAsciiString());
		}
		else
		{
			QueryString = _parsedQueryString;
		}
		return length2;
	}

	private void OnAuthorityFormTarget(HttpMethod method, Span<byte> target)
	{
		_requestTargetForm = HttpRequestTarget.AuthorityForm;
		if (HttpCharacters.ContainsInvalidAuthorityChar(target))
		{
			ThrowRequestTargetRejected(target);
		}
		if (method != HttpMethod.Connect)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.ConnectMethodRequired);
		}
		string parsedRawTarget = _parsedRawTarget;
		if (ServerOptions.DisableStringReuse || parsedRawTarget == null || parsedRawTarget.Length != target.Length || !StringUtilities.BytesOrdinalEqualsStringAndAscii(parsedRawTarget, target))
		{
			RawTarget = (_parsedRawTarget = target.GetAsciiString());
		}
		else
		{
			RawTarget = _parsedRawTarget;
		}
		Path = string.Empty;
		QueryString = string.Empty;
		_parsedPath = (_parsedQueryString = null);
		_parsedAbsoluteRequestTarget = null;
	}

	private void OnAsteriskFormTarget(HttpMethod method)
	{
		_requestTargetForm = HttpRequestTarget.AsteriskForm;
		if (method != HttpMethod.Options)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.OptionsMethodRequired);
		}
		RawTarget = "*";
		Path = string.Empty;
		QueryString = string.Empty;
		_parsedRawTarget = (_parsedPath = (_parsedQueryString = null));
		_parsedAbsoluteRequestTarget = null;
	}

	private void OnAbsoluteFormTarget(TargetOffsetPathLength targetPath, Span<byte> target)
	{
		int length = targetPath.Length;
		Span<byte> span = target.Slice(length, target.Length - length);
		_requestTargetForm = HttpRequestTarget.AbsoluteForm;
		bool disableStringReuse = ServerOptions.DisableStringReuse;
		string parsedRawTarget = _parsedRawTarget;
		if (disableStringReuse || parsedRawTarget == null || parsedRawTarget.Length != target.Length || !StringUtilities.BytesOrdinalEqualsStringAndAscii(parsedRawTarget, target))
		{
			try
			{
				RawTarget = (_parsedRawTarget = target.GetAsciiString());
			}
			catch (InvalidOperationException)
			{
				ThrowRequestTargetRejected(target);
			}
			if (!Uri.TryCreate(RawTarget, UriKind.Absolute, out Uri result))
			{
				ThrowRequestTargetRejected(target);
			}
			_absoluteRequestTarget = (_parsedAbsoluteRequestTarget = result);
			Path = (_parsedPath = result.LocalPath);
			parsedRawTarget = _parsedQueryString;
			if (disableStringReuse || parsedRawTarget == null || parsedRawTarget.Length != span.Length || !StringUtilities.BytesOrdinalEqualsStringAndAscii(parsedRawTarget, span))
			{
				QueryString = (_parsedQueryString = span.GetAsciiString());
			}
			else
			{
				QueryString = _parsedQueryString;
			}
		}
		else
		{
			RawTarget = _parsedRawTarget;
			Path = _parsedPath;
			QueryString = _parsedQueryString;
			_absoluteRequestTarget = _parsedAbsoluteRequestTarget;
		}
	}

	internal void EnsureHostHeaderExists()
	{
		int hostCount = HttpRequestHeaders.HostCount;
		string text = HttpRequestHeaders.HeaderHost.ToString();
		if (hostCount <= 0)
		{
			if (_httpVersion != Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http10)
			{
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.MissingHostHeader);
			}
		}
		else if (hostCount > 1)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.MultipleHostHeaders);
		}
		else if (_requestTargetForm != HttpRequestTarget.OriginForm)
		{
			ValidateNonOriginHostHeader(text);
		}
		else if (!HttpUtilities.IsHostHeaderValid(text))
		{
			KestrelMetrics.AddConnectionEndReason(MetricsContext, ConnectionEndReason.InvalidRequestHeaders);
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidHostHeader, text);
		}
	}

	private void ValidateNonOriginHostHeader(string hostText)
	{
		if (_requestTargetForm == HttpRequestTarget.AuthorityForm)
		{
			if (hostText != RawTarget)
			{
				KestrelMetrics.AddConnectionEndReason(MetricsContext, ConnectionEndReason.InvalidRequestHeaders);
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidHostHeader, hostText);
			}
		}
		else if (_requestTargetForm == HttpRequestTarget.AbsoluteForm)
		{
			string authority = _absoluteRequestTarget.Authority;
			if (hostText != authority && (!_absoluteRequestTarget.IsDefaultPort || hostText != $"{authority}:{_absoluteRequestTarget.Port}"))
			{
				if (_context.ServiceContext.ServerOptions.AllowHostHeaderOverride)
				{
					hostText = authority;
					HttpRequestHeaders.HeaderHost = hostText;
				}
				else
				{
					KestrelMetrics.AddConnectionEndReason(MetricsContext, ConnectionEndReason.InvalidRequestHeaders);
					KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidHostHeader, hostText);
				}
			}
		}
		if (!HttpUtilities.IsHostHeaderValid(hostText))
		{
			KestrelMetrics.AddConnectionEndReason(MetricsContext, ConnectionEndReason.InvalidRequestHeaders);
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidHostHeader, hostText);
		}
	}

	protected override void OnReset()
	{
		_requestTimedOut = false;
		_requestTargetForm = HttpRequestTarget.Unknown;
		_absoluteRequestTarget = null;
		_remainingRequestHeadersBytesAllowed = (long)ServerOptions.Limits.MaxRequestHeadersTotalSize + 2L;
		MinResponseDataRate = ServerOptions.Limits.MinResponseDataRate;
		_currentIHttpMinRequestBodyDataRateFeature = this;
		_currentIHttpMinResponseDataRateFeature = this;
		_currentIPersistentStateFeature = this;
	}

	protected override string CreateRequestId()
	{
		return StringUtilities.ConcatAsHexSuffix(ConnectionId, ':', _requestCount);
	}

	protected override MessageBody CreateMessageBody()
	{
		return Http1MessageBody.For(_httpVersion, HttpRequestHeaders, this);
	}

	protected override void BeginRequestProcessing()
	{
		Reset();
		_requestCount++;
		TimeoutControl.SetTimeout(ServerOptions.Limits.KeepAliveTimeout, TimeoutReason.KeepAlive);
	}

	protected override bool BeginRead(out ValueTask<ReadResult> awaitable)
	{
		awaitable = Input.ReadAsync();
		return true;
	}

	protected override bool TryParseRequest(ReadResult result, out bool endConnection)
	{
		SequenceReader<byte> reader = new SequenceReader<byte>(result.Buffer);
		bool flag = false;
		try
		{
			flag = ParseRequest(ref reader);
		}
		catch (InvalidOperationException) when (_requestProcessingStatus == RequestProcessingStatus.ParsingHeaders)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.MalformedRequestInvalidHeaders);
			throw;
		}
		catch (BadHttpRequestException ex2)
		{
			OnBadRequest(result.Buffer, ex2);
			throw;
		}
		catch (Exception)
		{
			KestrelMetrics.AddConnectionEndReason(MetricsContext, ConnectionEndReason.OtherError);
			throw;
		}
		finally
		{
			Input.AdvanceTo(reader.Position, flag ? reader.Position : result.Buffer.End);
		}
		if (result.IsCompleted)
		{
			switch (_requestProcessingStatus)
			{
			case RequestProcessingStatus.RequestPending:
				endConnection = true;
				return true;
			case RequestProcessingStatus.ParsingRequestLine:
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidRequestLine);
				break;
			case RequestProcessingStatus.ParsingHeaders:
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.MalformedRequestInvalidHeaders);
				break;
			}
		}
		else
		{
			if (!_keepAlive && _requestProcessingStatus == RequestProcessingStatus.RequestPending)
			{
				endConnection = true;
				return true;
			}
			if (RequestTimedOut)
			{
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.RequestHeadersTimeout);
			}
		}
		endConnection = false;
		if (_requestProcessingStatus == RequestProcessingStatus.AppStarted)
		{
			EnsureHostHeaderExists();
			return true;
		}
		return false;
	}

	internal static ConnectionEndReason GetConnectionEndReason(Microsoft.AspNetCore.Http.BadHttpRequestException ex)
	{
		switch ((ex as BadHttpRequestException)?.Reason)
		{
		case RequestRejectionReason.UnrecognizedHTTPVersion:
			return ConnectionEndReason.InvalidHttpVersion;
		case RequestRejectionReason.InvalidRequestLine:
		case RequestRejectionReason.InvalidRequestTarget:
		case RequestRejectionReason.RequestLineTooLong:
			return ConnectionEndReason.InvalidRequestLine;
		case RequestRejectionReason.InvalidRequestHeader:
		case RequestRejectionReason.InvalidRequestHeadersNoCRLF:
		case RequestRejectionReason.MalformedRequestInvalidHeaders:
		case RequestRejectionReason.InvalidContentLength:
		case RequestRejectionReason.MultipleContentLengths:
		case RequestRejectionReason.InvalidCharactersInHeaderName:
		case RequestRejectionReason.LengthRequiredHttp10:
		case RequestRejectionReason.OptionsMethodRequired:
		case RequestRejectionReason.ConnectMethodRequired:
		case RequestRejectionReason.MissingHostHeader:
		case RequestRejectionReason.MultipleHostHeaders:
		case RequestRejectionReason.InvalidHostHeader:
			return ConnectionEndReason.InvalidRequestHeaders;
		case RequestRejectionReason.HeadersExceedMaxTotalSize:
			return ConnectionEndReason.MaxRequestHeadersTotalSizeExceeded;
		case RequestRejectionReason.TooManyHeaders:
			return ConnectionEndReason.MaxRequestHeaderCountExceeded;
		case RequestRejectionReason.TlsOverHttpError:
			return ConnectionEndReason.TlsNotSupported;
		case RequestRejectionReason.UnexpectedEndOfRequestContent:
			return ConnectionEndReason.UnexpectedEndOfRequestContent;
		default:
			return ConnectionEndReason.OtherError;
		}
	}

	private void OnBadRequest(ReadOnlySequence<byte> requestData, BadHttpRequestException ex)
	{
		ConnectionEndReason connectionEndReason = GetConnectionEndReason(ex);
		KestrelMetrics.AddConnectionEndReason(MetricsContext, connectionEndReason);
		if (ex.Reason == RequestRejectionReason.UnrecognizedHTTPVersion)
		{
			DetectHttp2Preface(requestData);
		}
	}

	private void DetectHttp2Preface(ReadOnlySequence<byte> requestData)
	{
		if (ConnectionFeatures.Get<ITlsHandshakeFeature>() == null && _requestCount == 1 && requestData.Length >= 16)
		{
			ReadOnlySpan<byte> other = Http2Connection.ClientPreface.Slice(0, 16);
			if (requestData.Slice(0, 16).ToSpan().SequenceEqual(other))
			{
				Log.PossibleInvalidHttpVersionDetected(ConnectionId, Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http11, Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http2);
				_http2PrefaceDetected = true;
			}
		}
	}

	protected override Task TryProduceInvalidRequestResponse()
	{
		if (_http2PrefaceDetected)
		{
			_context.Transport.Output.Write(Http2GoAwayHttp11RequiredBytes);
			return _context.Transport.Output.FlushAsync().GetAsTask();
		}
		return base.TryProduceInvalidRequestResponse();
	}

	void IRequestProcessor.Tick(long timestamp)
	{
	}
}
