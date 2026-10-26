using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.IO;
using System.IO.Pipelines;
using System.Linq;
using System.Net;
using System.Runtime.CompilerServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Connections;
using Microsoft.AspNetCore.Connections.Features;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Http.Features.Authentication;
using Microsoft.AspNetCore.Http.Timeouts;
using Microsoft.AspNetCore.Internal;
using Microsoft.AspNetCore.Routing;
using Microsoft.AspNetCore.Server.Kestrel.Core.Features;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Primitives;
using Microsoft.Net.Http.Headers;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;

internal abstract class HttpProtocol : IHttpResponseControl, IFeatureCollection, IEnumerable<KeyValuePair<Type, object>>, IEnumerable, IHttpRequestFeature, IHttpResponseFeature, IHttpResponseBodyFeature, IRouteValuesFeature, IEndpointFeature, IHttpRequestIdentifierFeature, IHttpRequestTrailersFeature, IHttpExtendedConnectFeature, IHttpUpgradeFeature, IRequestBodyPipeFeature, IHttpConnectionFeature, IHttpRequestLifetimeFeature, IHttpBodyControlFeature, IHttpMaxRequestBodySizeFeature, IHttpRequestBodyDetectionFeature, IHttpWebTransportFeature, IBadRequestExceptionFeature
{
	private static readonly byte[] _bytesConnectionClose = Encoding.ASCII.GetBytes("\r\nConnection: close");

	private static readonly byte[] _bytesConnectionKeepAlive = Encoding.ASCII.GetBytes("\r\nConnection: keep-alive");

	private static readonly byte[] _bytesTransferEncodingChunked = Encoding.ASCII.GetBytes("\r\nTransfer-Encoding: chunked");

	private static readonly byte[] _bytesServer = Encoding.ASCII.GetBytes("\r\nServer: Kestrel");

	internal const string SchemeHttp = "http";

	internal const string SchemeHttps = "https";

	protected BodyControl? _bodyControl;

	private Stack<KeyValuePair<Func<object, Task>, object>> _onStarting;

	private Stack<KeyValuePair<Func<object, Task>, object>> _onCompleted;

	private readonly Lock _abortLock = new Lock();

	protected volatile bool _connectionAborted;

	private bool _preventRequestAbortedCancellation;

	private CancellationTokenSource _abortedCts;

	private CancellationToken? _manuallySetRequestAbortToken;

	protected RequestProcessingStatus _requestProcessingStatus;

	protected volatile bool _keepAlive = true;

	private ResponseBodyMode _responseBodyMode;

	private bool _hasAdvanced;

	private bool _isLeasedMemoryInvalid = true;

	protected Exception? _applicationException;

	private Microsoft.AspNetCore.Http.BadHttpRequestException _requestRejectedException;

	protected HttpVersion _httpVersion;

	private string _httpProtocol;

	private string _requestId;

	private int _requestHeadersParsed;

	protected int _eagerRequestHeadersParsedLimit;

	private long _responseBytesWritten;

	private HttpConnectionContext _context;

	private RouteValueDictionary _routeValues;

	private Endpoint _endpoint;

	protected string? _methodText;

	private string _scheme;

	private Stream _requestStreamInternal;

	private Stream _responseStreamInternal;

	private int _statusCode;

	private string _reasonPhrase;

	protected internal IHttpRequestFeature? _currentIHttpRequestFeature;

	protected internal IHttpResponseFeature? _currentIHttpResponseFeature;

	protected internal IHttpResponseBodyFeature? _currentIHttpResponseBodyFeature;

	protected internal IRouteValuesFeature? _currentIRouteValuesFeature;

	protected internal IEndpointFeature? _currentIEndpointFeature;

	protected internal IHttpRequestIdentifierFeature? _currentIHttpRequestIdentifierFeature;

	protected internal IHttpRequestTrailersFeature? _currentIHttpRequestTrailersFeature;

	protected internal IHttpExtendedConnectFeature? _currentIHttpExtendedConnectFeature;

	protected internal IHttpUpgradeFeature? _currentIHttpUpgradeFeature;

	protected internal IRequestBodyPipeFeature? _currentIRequestBodyPipeFeature;

	protected internal IHttpConnectionFeature? _currentIHttpConnectionFeature;

	protected internal IHttpRequestLifetimeFeature? _currentIHttpRequestLifetimeFeature;

	protected internal IHttpBodyControlFeature? _currentIHttpBodyControlFeature;

	protected internal IHttpMaxRequestBodySizeFeature? _currentIHttpMaxRequestBodySizeFeature;

	protected internal IHttpRequestBodyDetectionFeature? _currentIHttpRequestBodyDetectionFeature;

	protected internal IHttpWebTransportFeature? _currentIHttpWebTransportFeature;

	protected internal IBadRequestExceptionFeature? _currentIBadRequestExceptionFeature;

	protected internal IServiceProvidersFeature? _currentIServiceProvidersFeature;

	protected internal IHttpActivityFeature? _currentIHttpActivityFeature;

	protected internal IHttpMetricsTagsFeature? _currentIHttpMetricsTagsFeature;

	protected internal IItemsFeature? _currentIItemsFeature;

	protected internal IQueryFeature? _currentIQueryFeature;

	protected internal IFormFeature? _currentIFormFeature;

	protected internal IHttpAuthenticationFeature? _currentIHttpAuthenticationFeature;

	protected internal ISessionFeature? _currentISessionFeature;

	protected internal IResponseCookiesFeature? _currentIResponseCookiesFeature;

	protected internal IHttpResponseTrailersFeature? _currentIHttpResponseTrailersFeature;

	protected internal ITlsConnectionFeature? _currentITlsConnectionFeature;

	protected internal IHttpWebSocketFeature? _currentIHttpWebSocketFeature;

	protected internal IHttpRequestTimeoutFeature? _currentIHttpRequestTimeoutFeature;

	protected internal IHttp2StreamIdFeature? _currentIHttp2StreamIdFeature;

	protected internal IHttpMinRequestBodyDataRateFeature? _currentIHttpMinRequestBodyDataRateFeature;

	protected internal IHttpMinResponseDataRateFeature? _currentIHttpMinResponseDataRateFeature;

	protected internal IHttpResetFeature? _currentIHttpResetFeature;

	protected internal IPersistentStateFeature? _currentIPersistentStateFeature;

	private int _featureRevision;

	private List<KeyValuePair<Type, object>> MaybeExtra;

	public IHttpResponseControl HttpResponseControl { get; set; }

	public ServiceContext ServiceContext => _context.ServiceContext;

	private IPEndPoint? LocalEndPoint => _context.LocalEndPoint;

	private IPEndPoint? RemoteEndPoint => _context.RemoteEndPoint;

	public ITimeoutControl TimeoutControl => _context.TimeoutControl;

	public IFeatureCollection ConnectionFeatures => _context.ConnectionFeatures;

	public IHttpOutputProducer Output { get; protected set; }

	protected KestrelTrace Log => ServiceContext.Log;

	private DateHeaderValueManager DateHeaderValueManager => ServiceContext.DateHeaderValueManager;

	protected KestrelServerOptions ServerOptions { get; set; }

	protected string ConnectionId => _context.ConnectionId;

	public string ConnectionIdFeature { get; set; }

	public bool HasStartedConsumingRequestBody { get; set; }

	public long? MaxRequestBodySize { get; set; }

	public MinDataRate? MinRequestBodyDataRate { get; set; }

	public bool AllowSynchronousIO { get; set; }

	protected int RequestHeadersParsed => _requestHeadersParsed;

	public string TraceIdentifier
	{
		get
		{
			if (_requestId == null)
			{
				_requestId = CreateRequestId();
			}
			return _requestId;
		}
		set
		{
			_requestId = value;
		}
	}

	public bool IsUpgradableRequest { get; private set; }

	public bool IsUpgraded { get; set; }

	public bool IsExtendedConnectRequest { get; set; }

	public bool IsExtendedConnectAccepted { get; set; }

	public IPAddress? RemoteIpAddress { get; set; }

	public int RemotePort { get; set; }

	public IPAddress? LocalIpAddress { get; set; }

	public int LocalPort { get; set; }

	public string? ConnectProtocol { get; set; }

	public string? Scheme { get; set; }

	public HttpMethod Method { get; set; }

	public string MethodText => ((IHttpRequestFeature)this).Method;

	public string? PathBase { get; set; }

	public string? Path { get; set; }

	public string? QueryString { get; set; }

	public string? RawTarget { get; set; }

	public string HttpVersion
	{
		get
		{
			if (_httpVersion == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http3)
			{
				return Microsoft.AspNetCore.Http.HttpProtocol.Http3;
			}
			if (_httpVersion == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http2)
			{
				return Microsoft.AspNetCore.Http.HttpProtocol.Http2;
			}
			if (_httpVersion == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http11)
			{
				return Microsoft.AspNetCore.Http.HttpProtocol.Http11;
			}
			if (_httpVersion == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http10)
			{
				return Microsoft.AspNetCore.Http.HttpProtocol.Http10;
			}
			return string.Empty;
		}
		[MethodImpl(MethodImplOptions.AggressiveInlining)]
		set
		{
			if ((object)value == Microsoft.AspNetCore.Http.HttpProtocol.Http3)
			{
				_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http3;
			}
			else if ((object)value == Microsoft.AspNetCore.Http.HttpProtocol.Http2)
			{
				_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http2;
			}
			else if ((object)value == Microsoft.AspNetCore.Http.HttpProtocol.Http11)
			{
				_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http11;
			}
			else if ((object)value == Microsoft.AspNetCore.Http.HttpProtocol.Http10)
			{
				_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http10;
			}
			else
			{
				HttpVersionSetSlow(value);
			}
		}
	}

	public IHeaderDictionary RequestHeaders { get; set; }

	public IHeaderDictionary RequestTrailers { get; } = new HeaderDictionary();

	public bool RequestTrailersAvailable { get; set; }

	public Stream RequestBody { get; set; }

	public PipeReader RequestBodyPipeReader { get; set; }

	public HttpResponseTrailers? ResponseTrailers { get; set; }

	public int StatusCode
	{
		get
		{
			return _statusCode;
		}
		set
		{
			if (HasResponseStarted)
			{
				ThrowResponseAlreadyStartedException("StatusCode");
			}
			_statusCode = value;
		}
	}

	public string? ReasonPhrase
	{
		get
		{
			return _reasonPhrase;
		}
		set
		{
			if (HasResponseStarted)
			{
				ThrowResponseAlreadyStartedException("ReasonPhrase");
			}
			_reasonPhrase = value;
		}
	}

	public IHeaderDictionary ResponseHeaders { get; set; }

	public Stream ResponseBody { get; set; }

	public PipeWriter ResponseBodyPipeWriter { get; set; }

	public CancellationToken RequestAborted
	{
		get
		{
			if (_manuallySetRequestAbortToken.HasValue)
			{
				return _manuallySetRequestAbortToken.Value;
			}
			using (_abortLock.EnterScope())
			{
				if (_preventRequestAbortedCancellation)
				{
					return new CancellationToken(canceled: false);
				}
				if (_connectionAborted && _abortedCts == null)
				{
					return new CancellationToken(canceled: true);
				}
				if (_abortedCts == null)
				{
					_abortedCts = new CancellationTokenSource();
				}
				return _abortedCts.Token;
			}
		}
		set
		{
			_manuallySetRequestAbortToken = value;
		}
	}

	public bool HasResponseStarted => _requestProcessingStatus >= RequestProcessingStatus.HeadersCommitted;

	public bool HasFlushedHeaders => _requestProcessingStatus >= RequestProcessingStatus.HeadersFlushed;

	public bool HasResponseCompleted => _requestProcessingStatus == RequestProcessingStatus.ResponseCompleted;

	protected HttpRequestHeaders HttpRequestHeaders { get; set; } = new HttpRequestHeaders();

	protected HttpResponseHeaders HttpResponseHeaders { get; } = new HttpResponseHeaders();

	public long UnflushedBytes => Output.UnflushedBytes;

	string IHttpRequestFeature.Protocol
	{
		get
		{
			return _httpProtocol ?? (_httpProtocol = HttpVersion);
		}
		set
		{
			_httpProtocol = value;
		}
	}

	string IHttpRequestFeature.Scheme
	{
		get
		{
			return Scheme ?? "http";
		}
		set
		{
			Scheme = value;
		}
	}

	string IHttpRequestFeature.Method
	{
		get
		{
			if (_methodText != null)
			{
				return _methodText;
			}
			_methodText = HttpUtilities.MethodToString(Method) ?? string.Empty;
			return _methodText;
		}
		set
		{
			_methodText = value;
		}
	}

	string IHttpRequestFeature.PathBase
	{
		get
		{
			return PathBase ?? "";
		}
		set
		{
			PathBase = value;
		}
	}

	string IHttpRequestFeature.Path
	{
		get
		{
			return Path;
		}
		set
		{
			Path = value;
		}
	}

	string IHttpRequestFeature.QueryString
	{
		get
		{
			return QueryString;
		}
		set
		{
			QueryString = value;
		}
	}

	string IHttpRequestFeature.RawTarget
	{
		get
		{
			return RawTarget;
		}
		set
		{
			RawTarget = value;
		}
	}

	IHeaderDictionary IHttpRequestFeature.Headers
	{
		get
		{
			return RequestHeaders;
		}
		set
		{
			RequestHeaders = value;
		}
	}

	Stream IHttpRequestFeature.Body
	{
		get
		{
			return RequestBody;
		}
		set
		{
			RequestBody = value;
		}
	}

	PipeReader IRequestBodyPipeFeature.Reader
	{
		get
		{
			if (_requestStreamInternal != RequestBody)
			{
				_requestStreamInternal = RequestBody;
				RequestBodyPipeReader = PipeReader.Create(RequestBody, new StreamPipeReaderOptions(_context.MemoryPool, _context.MemoryPool.GetMinimumSegmentSize(), _context.MemoryPool.GetMinimumAllocSize(), leaveOpen: false, useZeroByteReads: true));
				OnCompleted((object self) =>
				{
					((PipeReader)self).Complete();
					return Task.CompletedTask;
				}, RequestBodyPipeReader);
			}
			return RequestBodyPipeReader;
		}
	}

	bool IHttpRequestBodyDetectionFeature.CanHaveBody => _bodyControl.CanHaveBody;

	bool IHttpRequestTrailersFeature.Available => RequestTrailersAvailable;

	IHeaderDictionary IHttpRequestTrailersFeature.Trailers
	{
		get
		{
			if (!RequestTrailersAvailable)
			{
				throw new InvalidOperationException(CoreStrings.RequestTrailersNotAvailable);
			}
			return RequestTrailers;
		}
	}

	int IHttpResponseFeature.StatusCode
	{
		get
		{
			return StatusCode;
		}
		set
		{
			StatusCode = value;
		}
	}

	string? IHttpResponseFeature.ReasonPhrase
	{
		get
		{
			return ReasonPhrase;
		}
		set
		{
			ReasonPhrase = value;
		}
	}

	IHeaderDictionary IHttpResponseFeature.Headers
	{
		get
		{
			return ResponseHeaders;
		}
		set
		{
			ResponseHeaders = value;
		}
	}

	CancellationToken IHttpRequestLifetimeFeature.RequestAborted
	{
		get
		{
			return RequestAborted;
		}
		set
		{
			RequestAborted = value;
		}
	}

	bool IHttpResponseFeature.HasStarted => HasResponseStarted;

	bool IHttpUpgradeFeature.IsUpgradableRequest => IsUpgradableRequest;

	bool IHttpExtendedConnectFeature.IsExtendedConnect => IsExtendedConnectRequest;

	string? IHttpExtendedConnectFeature.Protocol => ConnectProtocol;

	IPAddress? IHttpConnectionFeature.RemoteIpAddress
	{
		get
		{
			return RemoteIpAddress;
		}
		set
		{
			RemoteIpAddress = value;
		}
	}

	IPAddress? IHttpConnectionFeature.LocalIpAddress
	{
		get
		{
			return LocalIpAddress;
		}
		set
		{
			LocalIpAddress = value;
		}
	}

	int IHttpConnectionFeature.RemotePort
	{
		get
		{
			return RemotePort;
		}
		set
		{
			RemotePort = value;
		}
	}

	int IHttpConnectionFeature.LocalPort
	{
		get
		{
			return LocalPort;
		}
		set
		{
			LocalPort = value;
		}
	}

	string IHttpConnectionFeature.ConnectionId
	{
		get
		{
			return ConnectionIdFeature;
		}
		set
		{
			ConnectionIdFeature = value;
		}
	}

	string IHttpRequestIdentifierFeature.TraceIdentifier
	{
		get
		{
			return TraceIdentifier;
		}
		set
		{
			TraceIdentifier = value;
		}
	}

	bool IHttpBodyControlFeature.AllowSynchronousIO
	{
		get
		{
			return AllowSynchronousIO;
		}
		set
		{
			AllowSynchronousIO = value;
		}
	}

	bool IHttpMaxRequestBodySizeFeature.IsReadOnly
	{
		get
		{
			if (!HasStartedConsumingRequestBody && !IsUpgraded)
			{
				return IsExtendedConnectRequest;
			}
			return true;
		}
	}

	long? IHttpMaxRequestBodySizeFeature.MaxRequestBodySize
	{
		get
		{
			return MaxRequestBodySize;
		}
		set
		{
			if (HasStartedConsumingRequestBody)
			{
				throw new InvalidOperationException(CoreStrings.MaxRequestBodySizeCannotBeModifiedAfterRead);
			}
			if (IsUpgraded)
			{
				throw new InvalidOperationException(CoreStrings.MaxRequestBodySizeCannotBeModifiedForUpgradedRequests);
			}
			if (value < 0)
			{
				throw new ArgumentOutOfRangeException("value", CoreStrings.NonNegativeNumberOrNullRequired);
			}
			MaxRequestBodySize = value;
		}
	}

	Stream IHttpResponseFeature.Body
	{
		get
		{
			return ResponseBody;
		}
		set
		{
			ResponseBody = value;
		}
	}

	PipeWriter IHttpResponseBodyFeature.Writer => ResponseBodyPipeWriter;

	Endpoint? IEndpointFeature.Endpoint
	{
		get
		{
			return _endpoint;
		}
		set
		{
			_endpoint = value;
		}
	}

	RouteValueDictionary IRouteValuesFeature.RouteValues
	{
		get
		{
			return _routeValues ?? (_routeValues = new RouteValueDictionary());
		}
		set
		{
			_routeValues = value;
		}
	}

	Stream IHttpResponseBodyFeature.Stream => ResponseBody;

	Exception? IBadRequestExceptionFeature.Error => _requestRejectedException;

	public bool IsWebTransportRequest { get; set; }

	bool IFeatureCollection.IsReadOnly => false;

	int IFeatureCollection.Revision => _featureRevision;

	object? IFeatureCollection.this[Type key]
	{
		get
		{
			object obj = null;
			if (key == typeof(IHttpRequestFeature))
			{
				obj = _currentIHttpRequestFeature;
			}
			else if (key == typeof(IHttpResponseFeature))
			{
				obj = _currentIHttpResponseFeature;
			}
			else if (key == typeof(IHttpResponseBodyFeature))
			{
				obj = _currentIHttpResponseBodyFeature;
			}
			else if (key == typeof(IRouteValuesFeature))
			{
				obj = _currentIRouteValuesFeature;
			}
			else if (key == typeof(IEndpointFeature))
			{
				obj = _currentIEndpointFeature;
			}
			else if (key == typeof(IServiceProvidersFeature))
			{
				obj = _currentIServiceProvidersFeature;
			}
			else if (key == typeof(IHttpActivityFeature))
			{
				obj = _currentIHttpActivityFeature;
			}
			else if (key == typeof(IHttpMetricsTagsFeature))
			{
				obj = _currentIHttpMetricsTagsFeature;
			}
			else if (key == typeof(IItemsFeature))
			{
				obj = _currentIItemsFeature;
			}
			else if (key == typeof(IQueryFeature))
			{
				obj = _currentIQueryFeature;
			}
			else if (key == typeof(IRequestBodyPipeFeature))
			{
				obj = _currentIRequestBodyPipeFeature;
			}
			else if (key == typeof(IFormFeature))
			{
				obj = _currentIFormFeature;
			}
			else if (key == typeof(IHttpAuthenticationFeature))
			{
				obj = _currentIHttpAuthenticationFeature;
			}
			else if (key == typeof(IHttpRequestIdentifierFeature))
			{
				obj = _currentIHttpRequestIdentifierFeature;
			}
			else if (key == typeof(IHttpConnectionFeature))
			{
				obj = _currentIHttpConnectionFeature;
			}
			else if (key == typeof(ISessionFeature))
			{
				obj = _currentISessionFeature;
			}
			else if (key == typeof(IResponseCookiesFeature))
			{
				obj = _currentIResponseCookiesFeature;
			}
			else if (key == typeof(IHttpRequestTrailersFeature))
			{
				obj = _currentIHttpRequestTrailersFeature;
			}
			else if (key == typeof(IHttpResponseTrailersFeature))
			{
				obj = _currentIHttpResponseTrailersFeature;
			}
			else if (key == typeof(ITlsConnectionFeature))
			{
				obj = _currentITlsConnectionFeature;
			}
			else if (key == typeof(IHttpExtendedConnectFeature))
			{
				obj = _currentIHttpExtendedConnectFeature;
			}
			else if (key == typeof(IHttpUpgradeFeature))
			{
				obj = _currentIHttpUpgradeFeature;
			}
			else if (key == typeof(IHttpWebSocketFeature))
			{
				obj = _currentIHttpWebSocketFeature;
			}
			else if (key == typeof(IHttpWebTransportFeature))
			{
				obj = _currentIHttpWebTransportFeature;
			}
			else if (key == typeof(IBadRequestExceptionFeature))
			{
				obj = _currentIBadRequestExceptionFeature;
			}
			else if (key == typeof(IHttpRequestTimeoutFeature))
			{
				obj = _currentIHttpRequestTimeoutFeature;
			}
			else if (key == typeof(IHttp2StreamIdFeature))
			{
				obj = _currentIHttp2StreamIdFeature;
			}
			else if (key == typeof(IHttpRequestLifetimeFeature))
			{
				obj = _currentIHttpRequestLifetimeFeature;
			}
			else if (key == typeof(IHttpMaxRequestBodySizeFeature))
			{
				obj = _currentIHttpMaxRequestBodySizeFeature;
			}
			else if (key == typeof(IHttpMinRequestBodyDataRateFeature))
			{
				obj = _currentIHttpMinRequestBodyDataRateFeature;
			}
			else if (key == typeof(IHttpMinResponseDataRateFeature))
			{
				obj = _currentIHttpMinResponseDataRateFeature;
			}
			else if (key == typeof(IHttpBodyControlFeature))
			{
				obj = _currentIHttpBodyControlFeature;
			}
			else if (key == typeof(IHttpRequestBodyDetectionFeature))
			{
				obj = _currentIHttpRequestBodyDetectionFeature;
			}
			else if (key == typeof(IHttpResetFeature))
			{
				obj = _currentIHttpResetFeature;
			}
			else if (key == typeof(IPersistentStateFeature))
			{
				obj = _currentIPersistentStateFeature;
			}
			else if (MaybeExtra != null)
			{
				obj = ExtraFeatureGet(key);
			}
			object? obj2 = obj;
			if (obj2 == null)
			{
				IFeatureCollection connectionFeatures = ConnectionFeatures;
				if (connectionFeatures == null)
				{
					return null;
				}
				obj2 = connectionFeatures[key];
			}
			return obj2;
		}
		set
		{
			_featureRevision++;
			if (key == typeof(IHttpRequestFeature))
			{
				_currentIHttpRequestFeature = (IHttpRequestFeature)value;
			}
			else if (key == typeof(IHttpResponseFeature))
			{
				_currentIHttpResponseFeature = (IHttpResponseFeature)value;
			}
			else if (key == typeof(IHttpResponseBodyFeature))
			{
				_currentIHttpResponseBodyFeature = (IHttpResponseBodyFeature)value;
			}
			else if (key == typeof(IRouteValuesFeature))
			{
				_currentIRouteValuesFeature = (IRouteValuesFeature)value;
			}
			else if (key == typeof(IEndpointFeature))
			{
				_currentIEndpointFeature = (IEndpointFeature)value;
			}
			else if (key == typeof(IServiceProvidersFeature))
			{
				_currentIServiceProvidersFeature = (IServiceProvidersFeature)value;
			}
			else if (key == typeof(IHttpActivityFeature))
			{
				_currentIHttpActivityFeature = (IHttpActivityFeature)value;
			}
			else if (key == typeof(IHttpMetricsTagsFeature))
			{
				_currentIHttpMetricsTagsFeature = (IHttpMetricsTagsFeature)value;
			}
			else if (key == typeof(IItemsFeature))
			{
				_currentIItemsFeature = (IItemsFeature)value;
			}
			else if (key == typeof(IQueryFeature))
			{
				_currentIQueryFeature = (IQueryFeature)value;
			}
			else if (key == typeof(IRequestBodyPipeFeature))
			{
				_currentIRequestBodyPipeFeature = (IRequestBodyPipeFeature)value;
			}
			else if (key == typeof(IFormFeature))
			{
				_currentIFormFeature = (IFormFeature)value;
			}
			else if (key == typeof(IHttpAuthenticationFeature))
			{
				_currentIHttpAuthenticationFeature = (IHttpAuthenticationFeature)value;
			}
			else if (key == typeof(IHttpRequestIdentifierFeature))
			{
				_currentIHttpRequestIdentifierFeature = (IHttpRequestIdentifierFeature)value;
			}
			else if (key == typeof(IHttpConnectionFeature))
			{
				_currentIHttpConnectionFeature = (IHttpConnectionFeature)value;
			}
			else if (key == typeof(ISessionFeature))
			{
				_currentISessionFeature = (ISessionFeature)value;
			}
			else if (key == typeof(IResponseCookiesFeature))
			{
				_currentIResponseCookiesFeature = (IResponseCookiesFeature)value;
			}
			else if (key == typeof(IHttpRequestTrailersFeature))
			{
				_currentIHttpRequestTrailersFeature = (IHttpRequestTrailersFeature)value;
			}
			else if (key == typeof(IHttpResponseTrailersFeature))
			{
				_currentIHttpResponseTrailersFeature = (IHttpResponseTrailersFeature)value;
			}
			else if (key == typeof(ITlsConnectionFeature))
			{
				_currentITlsConnectionFeature = (ITlsConnectionFeature)value;
			}
			else if (key == typeof(IHttpExtendedConnectFeature))
			{
				_currentIHttpExtendedConnectFeature = (IHttpExtendedConnectFeature)value;
			}
			else if (key == typeof(IHttpUpgradeFeature))
			{
				_currentIHttpUpgradeFeature = (IHttpUpgradeFeature)value;
			}
			else if (key == typeof(IHttpWebSocketFeature))
			{
				_currentIHttpWebSocketFeature = (IHttpWebSocketFeature)value;
			}
			else if (key == typeof(IHttpWebTransportFeature))
			{
				_currentIHttpWebTransportFeature = (IHttpWebTransportFeature)value;
			}
			else if (key == typeof(IBadRequestExceptionFeature))
			{
				_currentIBadRequestExceptionFeature = (IBadRequestExceptionFeature)value;
			}
			else if (key == typeof(IHttpRequestTimeoutFeature))
			{
				_currentIHttpRequestTimeoutFeature = (IHttpRequestTimeoutFeature)value;
			}
			else if (key == typeof(IHttp2StreamIdFeature))
			{
				_currentIHttp2StreamIdFeature = (IHttp2StreamIdFeature)value;
			}
			else if (key == typeof(IHttpRequestLifetimeFeature))
			{
				_currentIHttpRequestLifetimeFeature = (IHttpRequestLifetimeFeature)value;
			}
			else if (key == typeof(IHttpMaxRequestBodySizeFeature))
			{
				_currentIHttpMaxRequestBodySizeFeature = (IHttpMaxRequestBodySizeFeature)value;
			}
			else if (key == typeof(IHttpMinRequestBodyDataRateFeature))
			{
				_currentIHttpMinRequestBodyDataRateFeature = (IHttpMinRequestBodyDataRateFeature)value;
			}
			else if (key == typeof(IHttpMinResponseDataRateFeature))
			{
				_currentIHttpMinResponseDataRateFeature = (IHttpMinResponseDataRateFeature)value;
			}
			else if (key == typeof(IHttpBodyControlFeature))
			{
				_currentIHttpBodyControlFeature = (IHttpBodyControlFeature)value;
			}
			else if (key == typeof(IHttpRequestBodyDetectionFeature))
			{
				_currentIHttpRequestBodyDetectionFeature = (IHttpRequestBodyDetectionFeature)value;
			}
			else if (key == typeof(IHttpResetFeature))
			{
				_currentIHttpResetFeature = (IHttpResetFeature)value;
			}
			else if (key == typeof(IPersistentStateFeature))
			{
				_currentIPersistentStateFeature = (IPersistentStateFeature)value;
			}
			else
			{
				ExtraFeatureSet(key, value);
			}
		}
	}

	public void Initialize(HttpConnectionContext context)
	{
		_context = context;
		ServerOptions = ServiceContext.ServerOptions;
		Reset();
		HttpResponseControl = this;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private void HttpVersionSetSlow(string value)
	{
		if (Microsoft.AspNetCore.Http.HttpProtocol.IsHttp3(value))
		{
			_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http3;
		}
		else if (Microsoft.AspNetCore.Http.HttpProtocol.IsHttp2(value))
		{
			_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http2;
		}
		else if (Microsoft.AspNetCore.Http.HttpProtocol.IsHttp11(value))
		{
			_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http11;
		}
		else if (Microsoft.AspNetCore.Http.HttpProtocol.IsHttp10(value))
		{
			_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http10;
		}
		else
		{
			_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Unknown;
		}
	}

	public void InitializeBodyControl(MessageBody messageBody)
	{
		if (_bodyControl == null)
		{
			_bodyControl = new BodyControl(this, this);
		}
		(Stream, Stream, PipeReader, PipeWriter) tuple = _bodyControl.Start(messageBody);
		RequestBody = tuple.Item1;
		ResponseBody = tuple.Item2;
		RequestBodyPipeReader = tuple.Item3;
		ResponseBodyPipeWriter = tuple.Item4;
		_requestStreamInternal = RequestBody;
		_responseStreamInternal = ResponseBody;
	}

	internal void ResetState()
	{
		_requestProcessingStatus = RequestProcessingStatus.RequestPending;
	}

	public void Reset()
	{
		_onStarting?.Clear();
		_onCompleted?.Clear();
		_routeValues?.Clear();
		_requestProcessingStatus = RequestProcessingStatus.RequestPending;
		_responseBodyMode = ResponseBodyMode.Uninitialized;
		_applicationException = null;
		_requestRejectedException = null;
		ResetFeatureCollection();
		HasStartedConsumingRequestBody = false;
		MaxRequestBodySize = ServerOptions.Limits.MaxRequestBodySize;
		MinRequestBodyDataRate = ServerOptions.Limits.MinRequestBodyDataRate;
		AllowSynchronousIO = ServerOptions.AllowSynchronousIO;
		TraceIdentifier = null;
		Method = HttpMethod.None;
		_methodText = null;
		_endpoint = null;
		PathBase = null;
		Path = null;
		RawTarget = null;
		QueryString = null;
		_httpVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Unknown;
		_httpProtocol = null;
		_statusCode = 200;
		_reasonPhrase = null;
		IsUpgraded = false;
		IsExtendedConnectRequest = false;
		IsExtendedConnectAccepted = false;
		IsWebTransportRequest = false;
		ConnectProtocol = null;
		IPEndPoint remoteEndPoint = RemoteEndPoint;
		RemoteIpAddress = remoteEndPoint?.Address;
		RemotePort = remoteEndPoint?.Port ?? 0;
		IPEndPoint localEndPoint = LocalEndPoint;
		LocalIpAddress = localEndPoint?.Address;
		LocalPort = localEndPoint?.Port ?? 0;
		ConnectionIdFeature = ConnectionId;
		HttpRequestHeaders.Reset();
		HttpRequestHeaders.EncodingSelector = ServerOptions.RequestHeaderEncodingSelector;
		HttpRequestHeaders.ReuseHeaderValues = !ServerOptions.DisableStringReuse;
		HttpResponseHeaders.Reset();
		HttpResponseHeaders.EncodingSelector = ServerOptions.ResponseHeaderEncodingSelector;
		RequestHeaders = HttpRequestHeaders;
		ResponseHeaders = HttpResponseHeaders;
		RequestTrailers.Clear();
		ResponseTrailers?.Reset();
		RequestTrailersAvailable = false;
		_isLeasedMemoryInvalid = true;
		_hasAdvanced = false;
		if (_scheme == null)
		{
			object obj = ConnectionFeatures?[typeof(ITlsConnectionFeature)];
			_scheme = ((obj != null) ? "https" : "http");
		}
		Scheme = _scheme;
		_manuallySetRequestAbortToken = null;
		using (_abortLock.EnterScope())
		{
			_preventRequestAbortedCancellation = false;
			if (!_connectionAborted && _abortedCts != null)
			{
				_abortedCts.TryReset();
			}
		}
		Output?.Reset();
		_requestHeadersParsed = 0;
		_eagerRequestHeadersParsedLimit = ServerOptions.Limits.MaxRequestHeaderCount;
		_responseBytesWritten = 0L;
		OnReset();
	}

	protected abstract void OnReset();

	protected abstract void ApplicationAbort();

	protected virtual void OnRequestProcessingEnded()
	{
	}

	protected virtual void BeginRequestProcessing()
	{
	}

	protected virtual void OnErrorAfterResponseStarted()
	{
	}

	protected virtual bool BeginRead(out ValueTask<ReadResult> awaitable)
	{
		awaitable = default;
		return false;
	}

	protected abstract string CreateRequestId();

	protected abstract MessageBody CreateMessageBody();

	protected abstract bool TryParseRequest(ReadResult result, out bool endConnection);

	private void CancelRequestAbortedTokenCallback()
	{
		try
		{
			CancellationTokenSource cancellationTokenSource = null;
			using (_abortLock.EnterScope())
			{
				if (_abortedCts != null && !_preventRequestAbortedCancellation)
				{
					cancellationTokenSource = _abortedCts;
				}
			}
			cancellationTokenSource?.Cancel();
		}
		catch (Exception ex)
		{
			Log.ApplicationError(ConnectionId, TraceIdentifier, ex);
		}
	}

	protected void CancelRequestAbortedToken()
	{
		bool flag = false;
		using (_abortLock.EnterScope())
		{
			if (_connectionAborted)
			{
				return;
			}
			flag = _abortedCts != null && !_preventRequestAbortedCancellation;
			_keepAlive = false;
			_connectionAborted = true;
		}
		if (flag)
		{
			ServiceContext.Scheduler.Schedule((object state) =>
			{
				((HttpProtocol)state).CancelRequestAbortedTokenCallback();
			}, this);
		}
	}

	protected void PoisonBody(Exception abortReason)
	{
		_bodyControl?.Abort(abortReason);
	}

	private void PreventRequestAbortedCancellation()
	{
		using (_abortLock.EnterScope())
		{
			if (!_connectionAborted)
			{
				_preventRequestAbortedCancellation = true;
			}
		}
	}

	public virtual void OnHeader(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value, bool checkForNewlineChars)
	{
		IncrementRequestHeadersCount();
		HttpRequestHeaders.Append(name, value, checkForNewlineChars);
	}

	public virtual void OnHeader(int index, bool indexOnly, ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		IncrementRequestHeadersCount();
	}

	public void OnTrailer(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value)
	{
		IncrementRequestHeadersCount();
		string headerName = name.GetHeaderName();
		string requestHeaderString = value.GetRequestHeaderString(headerName, HttpRequestHeaders.EncodingSelector, checkForNewlineChars: true);
		RequestTrailers.Append(headerName, requestHeaderString);
	}

	private void IncrementRequestHeadersCount()
	{
		_requestHeadersParsed++;
		if (_requestHeadersParsed > _eagerRequestHeadersParsedLimit)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.TooManyHeaders);
		}
	}

	public void OnHeadersComplete()
	{
		HttpRequestHeaders.OnHeadersComplete();
	}

	public void OnTrailersComplete()
	{
		RequestTrailersAvailable = true;
	}

	public async Task ProcessRequestsAsync<TContext>(IHttpApplication<TContext> application) where TContext : notnull
	{
		try
		{
			await ProcessRequests(application);
		}
		catch (Microsoft.AspNetCore.Http.BadHttpRequestException badRequestState)
		{
			SetBadRequestState(badRequestState);
		}
		catch (ConnectionResetException ex)
		{
			if (_requestProcessingStatus != RequestProcessingStatus.RequestPending)
			{
				Log.RequestProcessingError(ConnectionId, ex);
			}
		}
		catch (IOException ex2)
		{
			Log.RequestProcessingError(ConnectionId, ex2);
		}
		catch (ConnectionAbortedException ex3)
		{
			Log.RequestProcessingError(ConnectionId, ex3);
		}
		catch (Exception exception)
		{
			Log.LogWarning(0, exception, CoreStrings.RequestProcessingEndError);
		}
		finally
		{
			try
			{
				if (_requestRejectedException != null)
				{
					await TryProduceInvalidRequestResponse();
				}
			}
			catch (Exception exception2)
			{
				Log.LogWarning(0, exception2, CoreStrings.ConnectionShutdownError);
			}
			finally
			{
				OnRequestProcessingEnded();
			}
		}
	}

	private async Task ProcessRequests<TContext>(IHttpApplication<TContext> application)
	{
		while (_keepAlive)
		{
			if (_context.InitialExecutionContext == null)
			{
				_context.InitialExecutionContext = ExecutionContext.Capture();
			}
			else
			{
				ExecutionContext.Restore(_context.InitialExecutionContext);
			}
			BeginRequestProcessing();
			ReadResult result = default;
			bool endConnection;
			do
			{
				if (BeginRead(out var awaitable))
				{
					result = await awaitable;
				}
			}
			while (!TryParseRequest(result, out endConnection));
			if (endConnection)
			{
				break;
			}
			MessageBody messageBody = CreateMessageBody();
			if (!messageBody.RequestKeepAlive)
			{
				DisableKeepAlive(ConnectionEndReason.RequestNoKeepAlive);
			}
			IsUpgradableRequest = messageBody.RequestUpgrade;
			InitializeBodyControl(messageBody);
			TContext context = application.CreateContext(this);
			try
			{
				KestrelEventSource.Log.RequestStart(this);
				await application.ProcessRequestAsync(context);
				if (!HasResponseStarted && _applicationException == null)
				{
					Stack<KeyValuePair<Func<object, Task>, object>> onStarting = _onStarting;
					if (onStarting != null && onStarting.Count > 0)
					{
						await FireOnStarting();
					}
				}
				if (!_connectionAborted && !VerifyResponseContentLength(out Exception ex))
				{
					ReportApplicationError(ex);
				}
			}
			catch (Microsoft.AspNetCore.Http.BadHttpRequestException ex2)
			{
				SetBadRequestState(ex2);
				if (!_connectionAborted)
				{
					ReportApplicationError(ex2);
				}
			}
			catch (Exception ex3)
			{
				if ((ex3 is OperationCanceledException || ex3 is IOException) && _connectionAborted)
				{
					Log.RequestAborted(ConnectionId, TraceIdentifier);
				}
				else
				{
					ReportApplicationError(ex3);
				}
			}
			KestrelEventSource.Log.RequestStop(this);
			try
			{
				await _bodyControl.StopAsync();
			}
			catch (Exception ex4)
			{
				ReportApplicationError(ex4);
			}
			if (_requestRejectedException == null)
			{
				if (!_connectionAborted)
				{
					await ProduceEnd();
				}
				else if (!HasResponseStarted)
				{
					StatusCode = 499;
				}
			}
			Stack<KeyValuePair<Func<object, Task>, object>> onCompleted = _onCompleted;
			if (onCompleted != null && onCompleted.Count > 0)
			{
				await FireOnCompleted();
			}
			application.DisposeContext(context, _applicationException);
			if (!_connectionAborted && _requestRejectedException == null && !messageBody.IsEmpty)
			{
				await messageBody.ConsumeAsync();
			}
			if (HasStartedConsumingRequestBody)
			{
				await messageBody.StopAsync();
			}
		}
	}

	public void OnStarting(Func<object, Task> callback, object state)
	{
		if (HasResponseStarted)
		{
			ThrowResponseAlreadyStartedException("OnStarting");
		}
		if (_onStarting == null)
		{
			_onStarting = new Stack<KeyValuePair<Func<object, Task>, object>>();
		}
		_onStarting.Push(new KeyValuePair<Func<object, Task>, object>(callback, state));
	}

	public void OnCompleted(Func<object, Task> callback, object state)
	{
		if (_onCompleted == null)
		{
			_onCompleted = new Stack<KeyValuePair<Func<object, Task>, object>>();
		}
		_onCompleted.Push(new KeyValuePair<Func<object, Task>, object>(callback, state));
	}

	protected Task FireOnStarting()
	{
		Stack<KeyValuePair<Func<object, Task>, object>> onStarting = _onStarting;
		if (onStarting != null && onStarting.Count > 0)
		{
			return ProcessEvents(this, onStarting);
		}
		return Task.CompletedTask;
		static async Task ProcessEvents(HttpProtocol protocol, Stack<KeyValuePair<Func<object, Task>, object>> events)
		{
			try
			{
				KeyValuePair<Func<object, Task>, object> result;
				while (events.TryPop(out result))
				{
					await result.Key(result.Value);
				}
			}
			catch (Exception ex)
			{
				protocol.ReportApplicationError(ex);
			}
		}
	}

	protected Task FireOnCompleted()
	{
		Stack<KeyValuePair<Func<object, Task>, object>> onCompleted = _onCompleted;
		if (onCompleted != null && onCompleted.Count > 0)
		{
			return ProcessEvents(this, onCompleted);
		}
		return Task.CompletedTask;
		static async Task ProcessEvents(HttpProtocol protocol, Stack<KeyValuePair<Func<object, Task>, object>> events)
		{
			KeyValuePair<Func<object, Task>, object> result;
			while (events.TryPop(out result))
			{
				try
				{
					await result.Key(result.Value);
				}
				catch (Exception ex)
				{
					protocol.Log.ApplicationError(protocol.ConnectionId, protocol.TraceIdentifier, ex);
				}
			}
		}
	}

	private void VerifyAndUpdateWrite(int count)
	{
		HttpResponseHeaders httpResponseHeaders = HttpResponseHeaders;
		if (httpResponseHeaders != null && !httpResponseHeaders.HasTransferEncoding && httpResponseHeaders.ContentLength.HasValue && _responseBytesWritten + count > httpResponseHeaders.ContentLength.Value)
		{
			DisableKeepAlive(ConnectionEndReason.ResponseContentLengthMismatch);
			ThrowTooManyBytesWritten(count);
		}
		_responseBytesWritten += count;
	}

	[StackTraceHidden]
	private void ThrowTooManyBytesWritten(int count)
	{
		throw GetTooManyBytesWrittenException(count);
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private InvalidOperationException GetTooManyBytesWrittenException(int count)
	{
		HttpResponseHeaders httpResponseHeaders = HttpResponseHeaders;
		return new InvalidOperationException(CoreStrings.FormatTooManyBytesWritten(_responseBytesWritten + count, httpResponseHeaders.ContentLength.Value));
	}

	private void CheckLastWrite()
	{
		HttpResponseHeaders httpResponseHeaders = HttpResponseHeaders;
		if (httpResponseHeaders != null && !httpResponseHeaders.HasTransferEncoding && httpResponseHeaders.ContentLength.HasValue && _responseBytesWritten == httpResponseHeaders.ContentLength.Value)
		{
			PreventRequestAbortedCancellation();
		}
	}

	protected bool VerifyResponseContentLength([NotNullWhen(false)] out Exception? ex)
	{
		HttpResponseHeaders httpResponseHeaders = HttpResponseHeaders;
		if (Method != HttpMethod.Head && StatusCode != 304 && !httpResponseHeaders.HasTransferEncoding && httpResponseHeaders.ContentLength.HasValue && _responseBytesWritten < httpResponseHeaders.ContentLength.Value)
		{
			if (_responseBytesWritten > 0)
			{
				DisableKeepAlive(ConnectionEndReason.ResponseContentLengthMismatch);
			}
			ex = new InvalidOperationException(CoreStrings.FormatTooFewBytesWritten(_responseBytesWritten, httpResponseHeaders.ContentLength.Value));
			return false;
		}
		ex = null;
		return true;
	}

	public ValueTask<FlushResult> ProduceContinueAsync()
	{
		if (HasResponseStarted)
		{
			return default;
		}
		if (_httpVersion != Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http10 && ((IDictionary<string, StringValues>)HttpRequestHeaders).TryGetValue(HeaderNames.Expect, out StringValues value) && (value.FirstOrDefault() ?? "").Equals("100-continue", StringComparison.OrdinalIgnoreCase))
		{
			return Output.Write100ContinueAsync();
		}
		return default;
	}

	public Task InitializeResponseAsync(int firstWriteByteCount)
	{
		Task task = FireOnStarting();
		if (!task.IsCompletedSuccessfully)
		{
			return InitializeResponseAwaited(task, firstWriteByteCount);
		}
		VerifyInitializeState(firstWriteByteCount);
		ProduceStart(appCompleted: false);
		return Task.CompletedTask;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	public async Task InitializeResponseAwaited(Task startingTask, int firstWriteByteCount)
	{
		await startingTask;
		VerifyInitializeState(firstWriteByteCount);
		ProduceStart(appCompleted: false);
	}

	private HttpResponseHeaders InitializeResponseFirstWrite(int firstWriteByteCount)
	{
		VerifyInitializeState(firstWriteByteCount);
		HttpResponseHeaders result = CreateResponseHeaders(appCompleted: false);
		_requestProcessingStatus = RequestProcessingStatus.HeadersFlushed;
		return result;
	}

	private void ProduceStart(bool appCompleted)
	{
		if (!HasResponseStarted)
		{
			_isLeasedMemoryInvalid = true;
			_requestProcessingStatus = RequestProcessingStatus.HeadersCommitted;
			HttpResponseHeaders responseHeaders = CreateResponseHeaders(appCompleted);
			Output.WriteResponseHeaders(StatusCode, ReasonPhrase, responseHeaders, _responseBodyMode, appCompleted);
		}
	}

	private void VerifyInitializeState(int firstWriteByteCount)
	{
		if (_applicationException != null)
		{
			ThrowResponseAbortedException();
		}
		VerifyAndUpdateWrite(firstWriteByteCount);
	}

	protected virtual Task TryProduceInvalidRequestResponse()
	{
		if (!_connectionAborted)
		{
			return ProduceEnd();
		}
		return Task.CompletedTask;
	}

	protected Task ProduceEnd()
	{
		if (HasResponseCompleted)
		{
			return Task.CompletedTask;
		}
		_isLeasedMemoryInvalid = true;
		if (_requestRejectedException != null || _applicationException != null)
		{
			if (HasResponseStarted)
			{
				DisableKeepAlive(ConnectionEndReason.ErrorAfterStartingResponse);
				OnErrorAfterResponseStarted();
				return Task.CompletedTask;
			}
			if (_requestRejectedException != null)
			{
				SetErrorResponseException(_requestRejectedException);
			}
			else
			{
				SetErrorResponseHeaders(500);
			}
		}
		if (!HasResponseStarted)
		{
			ProduceStart(appCompleted: true);
		}
		return WriteSuffix();
	}

	private Task WriteSuffix()
	{
		if (_responseBodyMode == ResponseBodyMode.Chunked || _httpVersion >= Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http2)
		{
			PreventRequestAbortedCancellation();
		}
		ValueTask<FlushResult> writeTask = Output.WriteStreamSuffixAsync();
		if (!writeTask.IsCompletedSuccessfully)
		{
			return WriteSuffixAwaited(writeTask);
		}
		writeTask.GetAwaiter().GetResult();
		_requestProcessingStatus = RequestProcessingStatus.ResponseCompleted;
		if (_keepAlive)
		{
			Log.ConnectionKeepAlive(ConnectionId);
		}
		if (Method == HttpMethod.Head && _responseBytesWritten > 0)
		{
			Log.ConnectionHeadResponseBodyWrite(ConnectionId, _responseBytesWritten);
		}
		return Task.CompletedTask;
	}

	private async Task WriteSuffixAwaited(ValueTask<FlushResult> writeTask)
	{
		_requestProcessingStatus = RequestProcessingStatus.HeadersFlushed;
		await writeTask;
		_requestProcessingStatus = RequestProcessingStatus.ResponseCompleted;
		if (_keepAlive)
		{
			Log.ConnectionKeepAlive(ConnectionId);
		}
		if (Method == HttpMethod.Head && _responseBytesWritten > 0)
		{
			Log.ConnectionHeadResponseBodyWrite(ConnectionId, _responseBytesWritten);
		}
	}

	private HttpResponseHeaders CreateResponseHeaders(bool appCompleted)
	{
		HttpResponseHeaders httpResponseHeaders = HttpResponseHeaders;
		bool flag = httpResponseHeaders.HasConnection;
		bool flag2 = httpResponseHeaders.HasTransferEncoding;
		if (_httpVersion > Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http11 && httpResponseHeaders.HasInvalidH2H3Headers)
		{
			httpResponseHeaders.ClearInvalidH2H3Headers();
			flag2 = false;
			flag = false;
			Log.InvalidResponseHeaderRemoved();
		}
		if ((_keepAlive & flag) && (HttpHeaders.ParseConnection(httpResponseHeaders) & ConnectionOptions.KeepAlive) == 0)
		{
			DisableKeepAlive(ConnectionEndReason.ResponseNoKeepAlive);
		}
		if (flag2 && HttpHeaders.GetFinalTransferCoding(httpResponseHeaders.HeaderTransferEncoding) != TransferCoding.Chunked)
		{
			DisableKeepAlive(ConnectionEndReason.ResponseNoKeepAlive);
		}
		_responseBodyMode = ((!CanWriteResponseBody()) ? ResponseBodyMode.Disabled : ResponseBodyMode.ContentLength);
		if ((_responseBodyMode == ResponseBodyMode.Disabled) & flag2)
		{
			RejectInvalidHeaderForNonBodyResponse(appCompleted, HeaderNames.TransferEncoding);
		}
		else if (httpResponseHeaders.ContentLength.HasValue)
		{
			if (!CanIncludeResponseContentLengthHeader())
			{
				if (httpResponseHeaders.ContentLength.Value == 0L)
				{
					httpResponseHeaders.ContentLength = null;
				}
				else
				{
					RejectInvalidHeaderForNonBodyResponse(appCompleted, HeaderNames.ContentLength);
				}
			}
			else if (StatusCode == 205 && httpResponseHeaders.ContentLength.Value != 0L)
			{
				RejectNonzeroContentLengthOn205Response(appCompleted);
			}
		}
		else if (StatusCode == 101)
		{
			DisableKeepAlive(ConnectionEndReason.ResponseNoKeepAlive);
		}
		else if (!flag2 && !httpResponseHeaders.ContentLength.HasValue)
		{
			if ((appCompleted || _responseBodyMode == ResponseBodyMode.Disabled) && !_hasAdvanced)
			{
				if (CanAutoSetContentLengthZeroResponseHeader())
				{
					httpResponseHeaders.ContentLength = 0L;
				}
			}
			else if (_httpVersion == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http11)
			{
				if (_responseBodyMode == ResponseBodyMode.ContentLength)
				{
					_responseBodyMode = ResponseBodyMode.Chunked;
					httpResponseHeaders.SetRawTransferEncoding("chunked", _bytesTransferEncodingChunked);
				}
			}
			else
			{
				DisableKeepAlive(ConnectionEndReason.ResponseNoKeepAlive);
			}
		}
		httpResponseHeaders.SetReadOnly();
		if (!flag && _httpVersion < Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http2)
		{
			if (!_keepAlive)
			{
				httpResponseHeaders.SetRawConnection("close", _bytesConnectionClose);
			}
			else if (_httpVersion == Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http10)
			{
				httpResponseHeaders.SetRawConnection("keep-alive", _bytesConnectionKeepAlive);
			}
		}
		if (_context.AltSvcHeader != null && !httpResponseHeaders.HasAltSvc)
		{
			httpResponseHeaders.SetRawAltSvc(_context.AltSvcHeader.Value, _context.AltSvcHeader.RawBytes);
		}
		if (ServerOptions.AddServerHeader && !httpResponseHeaders.HasServer)
		{
			httpResponseHeaders.SetRawServer("Kestrel", _bytesServer);
		}
		if (!httpResponseHeaders.HasDate)
		{
			DateHeaderValueManager.DateHeaderValues dateHeaderValues = DateHeaderValueManager.GetDateHeaderValues();
			httpResponseHeaders.SetRawDate(dateHeaderValues.String, dateHeaderValues.Bytes);
		}
		return httpResponseHeaders;
	}

	private bool CanIncludeResponseContentLengthHeader()
	{
		if (Is1xxCode(StatusCode) || StatusCode == 204)
		{
			return false;
		}
		if (Method == HttpMethod.Connect && Is2xxCode(StatusCode))
		{
			return false;
		}
		return true;
		static bool Is1xxCode(int code)
		{
			if (code >= 100)
			{
				return code < 200;
			}
			return false;
		}
		static bool Is2xxCode(int code)
		{
			if (code >= 200)
			{
				return code < 300;
			}
			return false;
		}
	}

	private bool CanWriteResponseBody()
	{
		if (Method != HttpMethod.Head && StatusCode != 204 && StatusCode != 205)
		{
			return StatusCode != 304;
		}
		return false;
	}

	private bool CanAutoSetContentLengthZeroResponseHeader()
	{
		if (CanIncludeResponseContentLengthHeader() && Method != HttpMethod.Head)
		{
			return StatusCode != 304;
		}
		return false;
	}

	private static void ThrowResponseAlreadyStartedException(string value)
	{
		throw new InvalidOperationException(CoreStrings.FormatParameterReadOnlyAfterResponseStarted(value));
	}

	private void RejectInvalidHeaderForNonBodyResponse(bool appCompleted, string headerName)
	{
		RejectInvalidResponse(appCompleted, CoreStrings.FormatHeaderNotAllowedOnResponse(headerName, StatusCode));
	}

	private void RejectNonzeroContentLengthOn205Response(bool appCompleted)
	{
		RejectInvalidResponse(appCompleted, CoreStrings.NonzeroContentLengthNotAllowedOn205);
	}

	private void RejectInvalidResponse(bool appCompleted, string message)
	{
		InvalidOperationException ex = new InvalidOperationException(message);
		if (!appCompleted)
		{
			_requestProcessingStatus = RequestProcessingStatus.AppStarted;
			throw ex;
		}
		ReportApplicationError(ex);
		SetErrorResponseHeaders(500);
	}

	private void SetErrorResponseException(Microsoft.AspNetCore.Http.BadHttpRequestException ex)
	{
		SetErrorResponseHeaders(ex.StatusCode);
		if (ex is BadHttpRequestException ex2 && !StringValues.IsNullOrEmpty(ex2.AllowedHeader))
		{
			HttpResponseHeaders.HeaderAllow = ex2.AllowedHeader;
		}
	}

	private void SetErrorResponseHeaders(int statusCode)
	{
		StatusCode = statusCode;
		ReasonPhrase = null;
		HttpResponseHeaders httpResponseHeaders = HttpResponseHeaders;
		httpResponseHeaders.Reset();
		ResponseTrailers?.Reset();
		DateHeaderValueManager.DateHeaderValues dateHeaderValues = DateHeaderValueManager.GetDateHeaderValues();
		httpResponseHeaders.SetRawDate(dateHeaderValues.String, dateHeaderValues.Bytes);
		httpResponseHeaders.ContentLength = 0L;
		if (ServerOptions.AddServerHeader)
		{
			httpResponseHeaders.SetRawServer("Kestrel", _bytesServer);
		}
	}

	public void HandleNonBodyResponseWrite()
	{
		if (Method != HttpMethod.Head)
		{
			ThrowWritingToResponseBodyNotSupported();
		}
	}

	[StackTraceHidden]
	private void ThrowWritingToResponseBodyNotSupported()
	{
		throw new InvalidOperationException(CoreStrings.FormatWritingToResponseBodyNotSupported(StatusCode));
	}

	[StackTraceHidden]
	private void ThrowResponseAbortedException()
	{
		throw new ObjectDisposedException(CoreStrings.UnhandledApplicationException, _applicationException);
	}

	[StackTraceHidden]
	[DoesNotReturn]
	public void ThrowRequestTargetRejected(Span<byte> target)
	{
		throw GetInvalidRequestTargetException(target);
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private Microsoft.AspNetCore.Http.BadHttpRequestException GetInvalidRequestTargetException(ReadOnlySpan<byte> target)
	{
		return KestrelBadHttpRequestException.GetException(RequestRejectionReason.InvalidRequestTarget, Log.IsEnabled(LogLevel.Information) ? target.GetAsciiStringEscaped(128) : string.Empty);
	}

	public void SetBadRequestState(Microsoft.AspNetCore.Http.BadHttpRequestException ex)
	{
		Log.ConnectionBadRequest(ConnectionId, ex);
		_requestRejectedException = ex;
		if (!HasResponseStarted)
		{
			SetErrorResponseException(ex);
		}
		DiagnosticSource? diagnosticSource = ServiceContext.DiagnosticSource;
		if (diagnosticSource != null && diagnosticSource.IsEnabled("Microsoft.AspNetCore.Server.Kestrel.BadRequest"))
		{
			WriteDiagnosticEvent(ServiceContext.DiagnosticSource, "Microsoft.AspNetCore.Server.Kestrel.BadRequest", this);
		}
		DisableKeepAlive(Http1Connection.GetConnectionEndReason(ex));
	}

	internal virtual void DisableKeepAlive(ConnectionEndReason reason)
	{
		_keepAlive = false;
	}

	[UnconditionalSuppressMessage("ReflectionAnalysis", "IL2026:UnrecognizedReflectionPattern", Justification = "The values being passed into Write are being consumed by the application already.")]
	private static void WriteDiagnosticEvent(DiagnosticSource diagnosticSource, string name, HttpProtocol value)
	{
		diagnosticSource.Write(name, value);
	}

	public void ReportApplicationError(Exception? ex)
	{
		if (ex != null)
		{
			if (_applicationException == null)
			{
				_applicationException = ex;
			}
			else if (_applicationException is AggregateException)
			{
				_applicationException = new AggregateException(_applicationException, ex).Flatten();
			}
			else
			{
				_applicationException = new AggregateException(_applicationException, ex);
			}
			Log.ApplicationError(ConnectionId, TraceIdentifier, ex);
		}
	}

	public void Advance(int bytes)
	{
		if (bytes < 0)
		{
			throw new ArgumentOutOfRangeException("bytes");
		}
		if (bytes > 0)
		{
			_hasAdvanced = true;
		}
		if (_isLeasedMemoryInvalid)
		{
			throw new InvalidOperationException("Invalid ordering of calling StartAsync or CompleteAsync and Advance.");
		}
		if (_responseBodyMode != ResponseBodyMode.Disabled)
		{
			VerifyAndUpdateWrite(bytes);
			Output.Advance(bytes);
		}
		else
		{
			HandleNonBodyResponseWrite();
			VerifyAndUpdateWrite(bytes);
		}
	}

	public Memory<byte> GetMemory(int sizeHint = 0)
	{
		_isLeasedMemoryInvalid = false;
		return Output.GetMemory(sizeHint);
	}

	public Span<byte> GetSpan(int sizeHint = 0)
	{
		_isLeasedMemoryInvalid = false;
		return Output.GetSpan(sizeHint);
	}

	public ValueTask<FlushResult> FlushPipeAsync(CancellationToken cancellationToken)
	{
		if (!HasResponseStarted)
		{
			Task task = InitializeResponseAsync(0);
			if (!task.IsCompletedSuccessfully)
			{
				return FlushAsyncAwaited(task, cancellationToken);
			}
		}
		return Output.FlushAsync(cancellationToken);
	}

	public void CancelPendingFlush()
	{
		Output.CancelPendingFlush();
	}

	public Task CompleteAsync(Exception? exception = null)
	{
		if (exception != null)
		{
			ConnectionAbortedException ex = new ConnectionAbortedException("The BodyPipe was completed with an exception.", exception);
			ReportApplicationError(ex);
			if (HasResponseStarted)
			{
				ApplicationAbort();
			}
		}
		if (!HasResponseStarted)
		{
			Task task = FireOnStarting();
			if (!task.IsCompletedSuccessfully)
			{
				return CompleteAsyncAwaited(task);
			}
		}
		if (!HasResponseCompleted)
		{
			if (!VerifyResponseContentLength(out Exception ex2))
			{
				ThrowException(ex2);
			}
			return ProduceEnd();
		}
		return Task.CompletedTask;
	}

	private async Task CompleteAsyncAwaited(Task onStartingTask)
	{
		await onStartingTask;
		if (!HasResponseCompleted)
		{
			if (!VerifyResponseContentLength(out Exception ex))
			{
				ThrowException(ex);
			}
			await ProduceEnd();
		}
	}

	[StackTraceHidden]
	private static void ThrowException(Exception exception)
	{
		throw exception;
	}

	public ValueTask<FlushResult> WritePipeAsync(ReadOnlyMemory<byte> data, CancellationToken cancellationToken)
	{
		if (!HasResponseStarted)
		{
			return FirstWriteAsync(data, cancellationToken);
		}
		VerifyAndUpdateWrite(data.Length);
		switch (_responseBodyMode)
		{
		case ResponseBodyMode.Disabled:
			HandleNonBodyResponseWrite();
			return default;
		case ResponseBodyMode.Chunked:
			if (data.Length == 0)
			{
				return default;
			}
			return Output.WriteChunkAsync(data.Span, cancellationToken);
		case ResponseBodyMode.ContentLength:
			CheckLastWrite();
			return Output.WriteDataToPipeAsync(data.Span, cancellationToken);
		case ResponseBodyMode.Uninitialized:
			ThrowInvalidOperation();
			break;
		}
		return default;
	}

	private ValueTask<FlushResult> FirstWriteAsync(ReadOnlyMemory<byte> data, CancellationToken cancellationToken)
	{
		Task task = FireOnStarting();
		if (!task.IsCompletedSuccessfully)
		{
			return FirstWriteAsyncAwaited(task, data, cancellationToken);
		}
		return FirstWriteAsyncInternal(data, cancellationToken);
	}

	private async ValueTask<FlushResult> FirstWriteAsyncAwaited(Task initializeTask, ReadOnlyMemory<byte> data, CancellationToken cancellationToken)
	{
		await initializeTask;
		return await FirstWriteAsyncInternal(data, cancellationToken);
	}

	private ValueTask<FlushResult> FirstWriteAsyncInternal(ReadOnlyMemory<byte> data, CancellationToken cancellationToken)
	{
		HttpResponseHeaders responseHeaders = InitializeResponseFirstWrite(data.Length);
		switch (_responseBodyMode)
		{
		case ResponseBodyMode.Disabled:
			Output.WriteResponseHeaders(StatusCode, ReasonPhrase, responseHeaders, _responseBodyMode, appCompleted: false);
			HandleNonBodyResponseWrite();
			return Output.FlushAsync(cancellationToken);
		case ResponseBodyMode.Chunked:
			if (data.Length == 0)
			{
				Output.WriteResponseHeaders(StatusCode, ReasonPhrase, responseHeaders, _responseBodyMode, appCompleted: false);
				return Output.FlushAsync(cancellationToken);
			}
			return Output.FirstWriteChunkedAsync(StatusCode, ReasonPhrase, responseHeaders, _responseBodyMode, data.Span, cancellationToken);
		case ResponseBodyMode.ContentLength:
			CheckLastWrite();
			return Output.FirstWriteAsync(StatusCode, ReasonPhrase, responseHeaders, _responseBodyMode, data.Span, cancellationToken);
		case ResponseBodyMode.Uninitialized:
			ThrowInvalidOperation();
			break;
		}
		return default;
	}

	public Task FlushAsync(CancellationToken cancellationToken = default(CancellationToken))
	{
		return FlushPipeAsync(cancellationToken).GetAsTask();
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private async ValueTask<FlushResult> FlushAsyncAwaited(Task initializeTask, CancellationToken cancellationToken)
	{
		await initializeTask;
		return await Output.FlushAsync(cancellationToken);
	}

	public Task WriteAsync(ReadOnlyMemory<byte> data, CancellationToken cancellationToken = default(CancellationToken))
	{
		return WritePipeAsync(data, cancellationToken).GetAsTask();
	}

	public async ValueTask<FlushResult> WriteAsyncAwaited(Task initializeTask, ReadOnlyMemory<byte> data, CancellationToken cancellationToken)
	{
		await initializeTask;
		switch (_responseBodyMode)
		{
		case ResponseBodyMode.Disabled:
			HandleNonBodyResponseWrite();
			return await Output.FlushAsync(cancellationToken);
		case ResponseBodyMode.Chunked:
			if (data.Length == 0)
			{
				return await Output.FlushAsync(cancellationToken);
			}
			return await Output.WriteChunkAsync(data.Span, cancellationToken);
		case ResponseBodyMode.ContentLength:
			CheckLastWrite();
			return await Output.WriteDataToPipeAsync(data.Span, cancellationToken);
		case ResponseBodyMode.Uninitialized:
			ThrowInvalidOperation();
			break;
		}
		return default;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	[DoesNotReturn]
	private static void ThrowInvalidOperation()
	{
		throw new InvalidOperationException();
	}

	void IHttpResponseFeature.OnStarting(Func<object, Task> callback, object state)
	{
		OnStarting(callback, state);
	}

	void IHttpResponseFeature.OnCompleted(Func<object, Task> callback, object state)
	{
		OnCompleted(callback, state);
	}

	async Task<Stream> IHttpUpgradeFeature.UpgradeAsync()
	{
		if (!IsUpgradableRequest)
		{
			throw new InvalidOperationException(CoreStrings.CannotUpgradeNonUpgradableRequest);
		}
		if (IsUpgraded)
		{
			throw new InvalidOperationException(CoreStrings.UpgradeCannotBeCalledMultipleTimes);
		}
		if (!ServiceContext.ConnectionManager.UpgradedConnectionCount.TryLockOne())
		{
			throw new InvalidOperationException(CoreStrings.UpgradedConnectionLimitReached);
		}
		IsUpgraded = true;
		KestrelEventSource.Log.RequestUpgradedStart(this);
		ServiceContext.Metrics.RequestUpgradedStart(_context.MetricsContext);
		ConnectionFeatures.Get<IDecrementConcurrentConnectionCountFeature>()?.ReleaseConnection();
		StatusCode = 101;
		ReasonPhrase = "Switching Protocols";
		ResponseHeaders.Connection = HeaderNames.Upgrade;
		await FlushAsync();
		return _bodyControl.Upgrade();
	}

	async ValueTask<Stream> IHttpExtendedConnectFeature.AcceptAsync()
	{
		if (!IsExtendedConnectRequest)
		{
			throw new InvalidOperationException(CoreStrings.CannotAcceptNonConnectRequest);
		}
		if (IsExtendedConnectAccepted)
		{
			throw new InvalidOperationException(CoreStrings.AcceptCannotBeCalledMultipleTimes);
		}
		if (StatusCode < 200 || 300 <= StatusCode)
		{
			throw new InvalidOperationException(CoreStrings.ConnectStatusMustBe2XX);
		}
		IsExtendedConnectAccepted = true;
		await FlushAsync();
		return _bodyControl.AcceptConnect();
	}

	void IHttpRequestLifetimeFeature.Abort()
	{
		ApplicationAbort();
	}

	Task IHttpResponseBodyFeature.StartAsync(CancellationToken cancellationToken)
	{
		if (HasResponseStarted)
		{
			return Task.CompletedTask;
		}
		cancellationToken.ThrowIfCancellationRequested();
		return InitializeResponseAsync(0);
	}

	void IHttpResponseBodyFeature.DisableBuffering()
	{
	}

	Task IHttpResponseBodyFeature.SendFileAsync(string path, long offset, long? count, CancellationToken cancellation)
	{
		return SendFileFallback.SendFileAsync(ResponseBody, path, offset, count, cancellation);
	}

	Task IHttpResponseBodyFeature.CompleteAsync()
	{
		return CompleteAsync();
	}

	public virtual ValueTask<IWebTransportSession> AcceptAsync(CancellationToken token)
	{
		throw new NotSupportedException();
	}

	private void FastReset()
	{
		_currentIHttpRequestFeature = this;
		_currentIHttpResponseFeature = this;
		_currentIHttpResponseBodyFeature = this;
		_currentIRouteValuesFeature = this;
		_currentIEndpointFeature = this;
		_currentIHttpRequestIdentifierFeature = this;
		_currentIHttpRequestTrailersFeature = this;
		_currentIHttpExtendedConnectFeature = this;
		_currentIHttpUpgradeFeature = this;
		_currentIRequestBodyPipeFeature = this;
		_currentIHttpConnectionFeature = this;
		_currentIHttpRequestLifetimeFeature = this;
		_currentIHttpBodyControlFeature = this;
		_currentIHttpMaxRequestBodySizeFeature = this;
		_currentIHttpRequestBodyDetectionFeature = this;
		_currentIHttpWebTransportFeature = this;
		_currentIBadRequestExceptionFeature = this;
		_currentIServiceProvidersFeature = null;
		_currentIHttpActivityFeature = null;
		_currentIHttpMetricsTagsFeature = null;
		_currentIItemsFeature = null;
		_currentIQueryFeature = null;
		_currentIFormFeature = null;
		_currentIHttpAuthenticationFeature = null;
		_currentISessionFeature = null;
		_currentIResponseCookiesFeature = null;
		_currentIHttpResponseTrailersFeature = null;
		_currentITlsConnectionFeature = null;
		_currentIHttpWebSocketFeature = null;
		_currentIHttpRequestTimeoutFeature = null;
		_currentIHttp2StreamIdFeature = null;
		_currentIHttpMinRequestBodyDataRateFeature = null;
		_currentIHttpMinResponseDataRateFeature = null;
		_currentIHttpResetFeature = null;
		_currentIPersistentStateFeature = null;
	}

	internal void ResetFeatureCollection()
	{
		FastReset();
		MaybeExtra?.Clear();
		_featureRevision++;
	}

	private object ExtraFeatureGet(Type key)
	{
		if (MaybeExtra == null)
		{
			return null;
		}
		for (int i = 0; i < MaybeExtra.Count; i++)
		{
			KeyValuePair<Type, object> keyValuePair = MaybeExtra[i];
			if (keyValuePair.Key == key)
			{
				return keyValuePair.Value;
			}
		}
		return null;
	}

	private void ExtraFeatureSet(Type key, object value)
	{
		if (value == null)
		{
			if (MaybeExtra == null)
			{
				return;
			}
			for (int i = 0; i < MaybeExtra.Count; i++)
			{
				if (MaybeExtra[i].Key == key)
				{
					MaybeExtra.RemoveAt(i);
					break;
				}
			}
			return;
		}
		if (MaybeExtra == null)
		{
			MaybeExtra = new List<KeyValuePair<Type, object>>(2);
		}
		for (int j = 0; j < MaybeExtra.Count; j++)
		{
			if (MaybeExtra[j].Key == key)
			{
				MaybeExtra[j] = new KeyValuePair<Type, object>(key, value);
				return;
			}
		}
		MaybeExtra.Add(new KeyValuePair<Type, object>(key, value));
	}

	TFeature IFeatureCollection.Get<TFeature>()
	{
		TFeature val = default;
		if (typeof(TFeature) == typeof(IHttpRequestFeature))
		{
			val = Unsafe.As<IHttpRequestFeature, TFeature>(ref _currentIHttpRequestFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpResponseFeature))
		{
			val = Unsafe.As<IHttpResponseFeature, TFeature>(ref _currentIHttpResponseFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpResponseBodyFeature))
		{
			val = Unsafe.As<IHttpResponseBodyFeature, TFeature>(ref _currentIHttpResponseBodyFeature);
		}
		else if (typeof(TFeature) == typeof(IRouteValuesFeature))
		{
			val = Unsafe.As<IRouteValuesFeature, TFeature>(ref _currentIRouteValuesFeature);
		}
		else if (typeof(TFeature) == typeof(IEndpointFeature))
		{
			val = Unsafe.As<IEndpointFeature, TFeature>(ref _currentIEndpointFeature);
		}
		else if (typeof(TFeature) == typeof(IServiceProvidersFeature))
		{
			val = Unsafe.As<IServiceProvidersFeature, TFeature>(ref _currentIServiceProvidersFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpActivityFeature))
		{
			val = Unsafe.As<IHttpActivityFeature, TFeature>(ref _currentIHttpActivityFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpMetricsTagsFeature))
		{
			val = Unsafe.As<IHttpMetricsTagsFeature, TFeature>(ref _currentIHttpMetricsTagsFeature);
		}
		else if (typeof(TFeature) == typeof(IItemsFeature))
		{
			val = Unsafe.As<IItemsFeature, TFeature>(ref _currentIItemsFeature);
		}
		else if (typeof(TFeature) == typeof(IQueryFeature))
		{
			val = Unsafe.As<IQueryFeature, TFeature>(ref _currentIQueryFeature);
		}
		else if (typeof(TFeature) == typeof(IRequestBodyPipeFeature))
		{
			val = Unsafe.As<IRequestBodyPipeFeature, TFeature>(ref _currentIRequestBodyPipeFeature);
		}
		else if (typeof(TFeature) == typeof(IFormFeature))
		{
			val = Unsafe.As<IFormFeature, TFeature>(ref _currentIFormFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpAuthenticationFeature))
		{
			val = Unsafe.As<IHttpAuthenticationFeature, TFeature>(ref _currentIHttpAuthenticationFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestIdentifierFeature))
		{
			val = Unsafe.As<IHttpRequestIdentifierFeature, TFeature>(ref _currentIHttpRequestIdentifierFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpConnectionFeature))
		{
			val = Unsafe.As<IHttpConnectionFeature, TFeature>(ref _currentIHttpConnectionFeature);
		}
		else if (typeof(TFeature) == typeof(ISessionFeature))
		{
			val = Unsafe.As<ISessionFeature, TFeature>(ref _currentISessionFeature);
		}
		else if (typeof(TFeature) == typeof(IResponseCookiesFeature))
		{
			val = Unsafe.As<IResponseCookiesFeature, TFeature>(ref _currentIResponseCookiesFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestTrailersFeature))
		{
			val = Unsafe.As<IHttpRequestTrailersFeature, TFeature>(ref _currentIHttpRequestTrailersFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpResponseTrailersFeature))
		{
			val = Unsafe.As<IHttpResponseTrailersFeature, TFeature>(ref _currentIHttpResponseTrailersFeature);
		}
		else if (typeof(TFeature) == typeof(ITlsConnectionFeature))
		{
			val = Unsafe.As<ITlsConnectionFeature, TFeature>(ref _currentITlsConnectionFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpExtendedConnectFeature))
		{
			val = Unsafe.As<IHttpExtendedConnectFeature, TFeature>(ref _currentIHttpExtendedConnectFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpUpgradeFeature))
		{
			val = Unsafe.As<IHttpUpgradeFeature, TFeature>(ref _currentIHttpUpgradeFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpWebSocketFeature))
		{
			val = Unsafe.As<IHttpWebSocketFeature, TFeature>(ref _currentIHttpWebSocketFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpWebTransportFeature))
		{
			val = Unsafe.As<IHttpWebTransportFeature, TFeature>(ref _currentIHttpWebTransportFeature);
		}
		else if (typeof(TFeature) == typeof(IBadRequestExceptionFeature))
		{
			val = Unsafe.As<IBadRequestExceptionFeature, TFeature>(ref _currentIBadRequestExceptionFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestTimeoutFeature))
		{
			val = Unsafe.As<IHttpRequestTimeoutFeature, TFeature>(ref _currentIHttpRequestTimeoutFeature);
		}
		else if (typeof(TFeature) == typeof(IHttp2StreamIdFeature))
		{
			val = Unsafe.As<IHttp2StreamIdFeature, TFeature>(ref _currentIHttp2StreamIdFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestLifetimeFeature))
		{
			val = Unsafe.As<IHttpRequestLifetimeFeature, TFeature>(ref _currentIHttpRequestLifetimeFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpMaxRequestBodySizeFeature))
		{
			val = Unsafe.As<IHttpMaxRequestBodySizeFeature, TFeature>(ref _currentIHttpMaxRequestBodySizeFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpMinRequestBodyDataRateFeature))
		{
			val = Unsafe.As<IHttpMinRequestBodyDataRateFeature, TFeature>(ref _currentIHttpMinRequestBodyDataRateFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpMinResponseDataRateFeature))
		{
			val = Unsafe.As<IHttpMinResponseDataRateFeature, TFeature>(ref _currentIHttpMinResponseDataRateFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpBodyControlFeature))
		{
			val = Unsafe.As<IHttpBodyControlFeature, TFeature>(ref _currentIHttpBodyControlFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestBodyDetectionFeature))
		{
			val = Unsafe.As<IHttpRequestBodyDetectionFeature, TFeature>(ref _currentIHttpRequestBodyDetectionFeature);
		}
		else if (typeof(TFeature) == typeof(IHttpResetFeature))
		{
			val = Unsafe.As<IHttpResetFeature, TFeature>(ref _currentIHttpResetFeature);
		}
		else if (typeof(TFeature) == typeof(IPersistentStateFeature))
		{
			val = Unsafe.As<IPersistentStateFeature, TFeature>(ref _currentIPersistentStateFeature);
		}
		else if (MaybeExtra != null)
		{
			val = (TFeature)ExtraFeatureGet(typeof(TFeature));
		}
		if (val == null && ConnectionFeatures != null)
		{
			val = ConnectionFeatures.Get<TFeature>();
		}
		return val;
	}

	void IFeatureCollection.Set<TFeature>(TFeature feature)
	{
		_featureRevision++;
		if (typeof(TFeature) == typeof(IHttpRequestFeature))
		{
			_currentIHttpRequestFeature = Unsafe.As<TFeature, IHttpRequestFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpResponseFeature))
		{
			_currentIHttpResponseFeature = Unsafe.As<TFeature, IHttpResponseFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpResponseBodyFeature))
		{
			_currentIHttpResponseBodyFeature = Unsafe.As<TFeature, IHttpResponseBodyFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IRouteValuesFeature))
		{
			_currentIRouteValuesFeature = Unsafe.As<TFeature, IRouteValuesFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IEndpointFeature))
		{
			_currentIEndpointFeature = Unsafe.As<TFeature, IEndpointFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IServiceProvidersFeature))
		{
			_currentIServiceProvidersFeature = Unsafe.As<TFeature, IServiceProvidersFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpActivityFeature))
		{
			_currentIHttpActivityFeature = Unsafe.As<TFeature, IHttpActivityFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpMetricsTagsFeature))
		{
			_currentIHttpMetricsTagsFeature = Unsafe.As<TFeature, IHttpMetricsTagsFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IItemsFeature))
		{
			_currentIItemsFeature = Unsafe.As<TFeature, IItemsFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IQueryFeature))
		{
			_currentIQueryFeature = Unsafe.As<TFeature, IQueryFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IRequestBodyPipeFeature))
		{
			_currentIRequestBodyPipeFeature = Unsafe.As<TFeature, IRequestBodyPipeFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IFormFeature))
		{
			_currentIFormFeature = Unsafe.As<TFeature, IFormFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpAuthenticationFeature))
		{
			_currentIHttpAuthenticationFeature = Unsafe.As<TFeature, IHttpAuthenticationFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestIdentifierFeature))
		{
			_currentIHttpRequestIdentifierFeature = Unsafe.As<TFeature, IHttpRequestIdentifierFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpConnectionFeature))
		{
			_currentIHttpConnectionFeature = Unsafe.As<TFeature, IHttpConnectionFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(ISessionFeature))
		{
			_currentISessionFeature = Unsafe.As<TFeature, ISessionFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IResponseCookiesFeature))
		{
			_currentIResponseCookiesFeature = Unsafe.As<TFeature, IResponseCookiesFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestTrailersFeature))
		{
			_currentIHttpRequestTrailersFeature = Unsafe.As<TFeature, IHttpRequestTrailersFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpResponseTrailersFeature))
		{
			_currentIHttpResponseTrailersFeature = Unsafe.As<TFeature, IHttpResponseTrailersFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(ITlsConnectionFeature))
		{
			_currentITlsConnectionFeature = Unsafe.As<TFeature, ITlsConnectionFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpExtendedConnectFeature))
		{
			_currentIHttpExtendedConnectFeature = Unsafe.As<TFeature, IHttpExtendedConnectFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpUpgradeFeature))
		{
			_currentIHttpUpgradeFeature = Unsafe.As<TFeature, IHttpUpgradeFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpWebSocketFeature))
		{
			_currentIHttpWebSocketFeature = Unsafe.As<TFeature, IHttpWebSocketFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpWebTransportFeature))
		{
			_currentIHttpWebTransportFeature = Unsafe.As<TFeature, IHttpWebTransportFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IBadRequestExceptionFeature))
		{
			_currentIBadRequestExceptionFeature = Unsafe.As<TFeature, IBadRequestExceptionFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestTimeoutFeature))
		{
			_currentIHttpRequestTimeoutFeature = Unsafe.As<TFeature, IHttpRequestTimeoutFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttp2StreamIdFeature))
		{
			_currentIHttp2StreamIdFeature = Unsafe.As<TFeature, IHttp2StreamIdFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestLifetimeFeature))
		{
			_currentIHttpRequestLifetimeFeature = Unsafe.As<TFeature, IHttpRequestLifetimeFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpMaxRequestBodySizeFeature))
		{
			_currentIHttpMaxRequestBodySizeFeature = Unsafe.As<TFeature, IHttpMaxRequestBodySizeFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpMinRequestBodyDataRateFeature))
		{
			_currentIHttpMinRequestBodyDataRateFeature = Unsafe.As<TFeature, IHttpMinRequestBodyDataRateFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpMinResponseDataRateFeature))
		{
			_currentIHttpMinResponseDataRateFeature = Unsafe.As<TFeature, IHttpMinResponseDataRateFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpBodyControlFeature))
		{
			_currentIHttpBodyControlFeature = Unsafe.As<TFeature, IHttpBodyControlFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpRequestBodyDetectionFeature))
		{
			_currentIHttpRequestBodyDetectionFeature = Unsafe.As<TFeature, IHttpRequestBodyDetectionFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IHttpResetFeature))
		{
			_currentIHttpResetFeature = Unsafe.As<TFeature, IHttpResetFeature>(ref feature);
		}
		else if (typeof(TFeature) == typeof(IPersistentStateFeature))
		{
			_currentIPersistentStateFeature = Unsafe.As<TFeature, IPersistentStateFeature>(ref feature);
		}
		else
		{
			ExtraFeatureSet(typeof(TFeature), feature);
		}
	}

	private IEnumerable<KeyValuePair<Type, object>> FastEnumerable()
	{
		if (_currentIHttpRequestFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpRequestFeature), _currentIHttpRequestFeature);
		}
		if (_currentIHttpResponseFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpResponseFeature), _currentIHttpResponseFeature);
		}
		if (_currentIHttpResponseBodyFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpResponseBodyFeature), _currentIHttpResponseBodyFeature);
		}
		if (_currentIRouteValuesFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IRouteValuesFeature), _currentIRouteValuesFeature);
		}
		if (_currentIEndpointFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IEndpointFeature), _currentIEndpointFeature);
		}
		if (_currentIServiceProvidersFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IServiceProvidersFeature), _currentIServiceProvidersFeature);
		}
		if (_currentIHttpActivityFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpActivityFeature), _currentIHttpActivityFeature);
		}
		if (_currentIHttpMetricsTagsFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpMetricsTagsFeature), _currentIHttpMetricsTagsFeature);
		}
		if (_currentIItemsFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IItemsFeature), _currentIItemsFeature);
		}
		if (_currentIQueryFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IQueryFeature), _currentIQueryFeature);
		}
		if (_currentIRequestBodyPipeFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IRequestBodyPipeFeature), _currentIRequestBodyPipeFeature);
		}
		if (_currentIFormFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IFormFeature), _currentIFormFeature);
		}
		if (_currentIHttpAuthenticationFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpAuthenticationFeature), _currentIHttpAuthenticationFeature);
		}
		if (_currentIHttpRequestIdentifierFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpRequestIdentifierFeature), _currentIHttpRequestIdentifierFeature);
		}
		if (_currentIHttpConnectionFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpConnectionFeature), _currentIHttpConnectionFeature);
		}
		if (_currentISessionFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(ISessionFeature), _currentISessionFeature);
		}
		if (_currentIResponseCookiesFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IResponseCookiesFeature), _currentIResponseCookiesFeature);
		}
		if (_currentIHttpRequestTrailersFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpRequestTrailersFeature), _currentIHttpRequestTrailersFeature);
		}
		if (_currentIHttpResponseTrailersFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpResponseTrailersFeature), _currentIHttpResponseTrailersFeature);
		}
		if (_currentITlsConnectionFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(ITlsConnectionFeature), _currentITlsConnectionFeature);
		}
		if (_currentIHttpExtendedConnectFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpExtendedConnectFeature), _currentIHttpExtendedConnectFeature);
		}
		if (_currentIHttpUpgradeFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpUpgradeFeature), _currentIHttpUpgradeFeature);
		}
		if (_currentIHttpWebSocketFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpWebSocketFeature), _currentIHttpWebSocketFeature);
		}
		if (_currentIHttpWebTransportFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpWebTransportFeature), _currentIHttpWebTransportFeature);
		}
		if (_currentIBadRequestExceptionFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IBadRequestExceptionFeature), _currentIBadRequestExceptionFeature);
		}
		if (_currentIHttpRequestTimeoutFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpRequestTimeoutFeature), _currentIHttpRequestTimeoutFeature);
		}
		if (_currentIHttp2StreamIdFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttp2StreamIdFeature), _currentIHttp2StreamIdFeature);
		}
		if (_currentIHttpRequestLifetimeFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpRequestLifetimeFeature), _currentIHttpRequestLifetimeFeature);
		}
		if (_currentIHttpMaxRequestBodySizeFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpMaxRequestBodySizeFeature), _currentIHttpMaxRequestBodySizeFeature);
		}
		if (_currentIHttpMinRequestBodyDataRateFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpMinRequestBodyDataRateFeature), _currentIHttpMinRequestBodyDataRateFeature);
		}
		if (_currentIHttpMinResponseDataRateFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpMinResponseDataRateFeature), _currentIHttpMinResponseDataRateFeature);
		}
		if (_currentIHttpBodyControlFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpBodyControlFeature), _currentIHttpBodyControlFeature);
		}
		if (_currentIHttpRequestBodyDetectionFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpRequestBodyDetectionFeature), _currentIHttpRequestBodyDetectionFeature);
		}
		if (_currentIHttpResetFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IHttpResetFeature), _currentIHttpResetFeature);
		}
		if (_currentIPersistentStateFeature != null)
		{
			yield return new KeyValuePair<Type, object>(typeof(IPersistentStateFeature), _currentIPersistentStateFeature);
		}
		if (MaybeExtra == null)
		{
			yield break;
		}
		foreach (KeyValuePair<Type, object> item in MaybeExtra)
		{
			yield return item;
		}
	}

	IEnumerator<KeyValuePair<Type, object>> IEnumerable<KeyValuePair<Type, object>>.GetEnumerator()
	{
		return FastEnumerable().GetEnumerator();
	}

	IEnumerator IEnumerable.GetEnumerator()
	{
		return FastEnumerable().GetEnumerator();
	}
}
