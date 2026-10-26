using System;
using System.Buffers.Binary;
using System.Buffers.Text;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Numerics;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;
using Microsoft.Extensions.Primitives;
using Microsoft.Net.Http.Headers;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;

internal sealed class HttpRequestHeaders : HttpHeaders, IHeaderDictionary, IDictionary<string, StringValues>, ICollection<KeyValuePair<string, StringValues>>, IEnumerable<KeyValuePair<string, StringValues>>, IEnumerable
{
	private struct HeaderReferences
	{
		public StringValues _Accept;

		public StringValues _Connection;

		public StringValues _Host;

		public StringValues _UserAgent;

		public StringValues _Authority;

		public StringValues _Method;

		public StringValues _Path;

		public StringValues _Protocol;

		public StringValues _Scheme;

		public StringValues _AcceptCharset;

		public StringValues _AcceptEncoding;

		public StringValues _AcceptLanguage;

		public StringValues _AccessControlRequestHeaders;

		public StringValues _AccessControlRequestMethod;

		public StringValues _AltUsed;

		public StringValues _Authorization;

		public StringValues _Baggage;

		public StringValues _CacheControl;

		public StringValues _ContentType;

		public StringValues _Cookie;

		public StringValues _CorrelationContext;

		public StringValues _Date;

		public StringValues _Expect;

		public StringValues _From;

		public StringValues _GrpcAcceptEncoding;

		public StringValues _GrpcEncoding;

		public StringValues _GrpcTimeout;

		public StringValues _IfMatch;

		public StringValues _IfModifiedSince;

		public StringValues _IfNoneMatch;

		public StringValues _IfRange;

		public StringValues _IfUnmodifiedSince;

		public StringValues _KeepAlive;

		public StringValues _MaxForwards;

		public StringValues _Origin;

		public StringValues _Pragma;

		public StringValues _ProxyAuthorization;

		public StringValues _Range;

		public StringValues _Referer;

		public StringValues _RequestId;

		public StringValues _TE;

		public StringValues _TraceParent;

		public StringValues _TraceState;

		public StringValues _TransferEncoding;

		public StringValues _Translate;

		public StringValues _Upgrade;

		public StringValues _UpgradeInsecureRequests;

		public StringValues _Via;

		public StringValues _Warning;
	}

	public struct Enumerator : IEnumerator<KeyValuePair<string, StringValues>>, IEnumerator, IDisposable
	{
		private readonly HttpRequestHeaders _collection;

		private long _currentBits;

		private int _next;

		private KeyValuePair<string, StringValues> _current;

		private readonly bool _hasUnknown;

		private Dictionary<string, StringValues>.Enumerator _unknownEnumerator;

		public readonly KeyValuePair<string, StringValues> Current => _current;

		readonly object IEnumerator.Current => _current;

		public bool MoveNext()
		{
			switch (_next)
			{
			case 0:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Accept, _collection._headers._Accept);
				_currentBits ^= 1L;
				break;
			case 1:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Connection, _collection._headers._Connection);
				_currentBits ^= 2L;
				break;
			case 2:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Host, _collection._headers._Host);
				_currentBits ^= 4L;
				break;
			case 3:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.UserAgent, _collection._headers._UserAgent);
				_currentBits ^= 8L;
				break;
			case 4:
				_current = new KeyValuePair<string, StringValues>(InternalHeaderNames.Authority, _collection._headers._Authority);
				_currentBits ^= 16L;
				break;
			case 5:
				_current = new KeyValuePair<string, StringValues>(InternalHeaderNames.Method, _collection._headers._Method);
				_currentBits ^= 32L;
				break;
			case 6:
				_current = new KeyValuePair<string, StringValues>(InternalHeaderNames.Path, _collection._headers._Path);
				_currentBits ^= 64L;
				break;
			case 7:
				_current = new KeyValuePair<string, StringValues>(InternalHeaderNames.Protocol, _collection._headers._Protocol);
				_currentBits ^= 128L;
				break;
			case 8:
				_current = new KeyValuePair<string, StringValues>(InternalHeaderNames.Scheme, _collection._headers._Scheme);
				_currentBits ^= 256L;
				break;
			case 9:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.AcceptCharset, _collection._headers._AcceptCharset);
				_currentBits ^= 512L;
				break;
			case 10:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.AcceptEncoding, _collection._headers._AcceptEncoding);
				_currentBits ^= 1024L;
				break;
			case 11:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.AcceptLanguage, _collection._headers._AcceptLanguage);
				_currentBits ^= 2048L;
				break;
			case 12:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.AccessControlRequestHeaders, _collection._headers._AccessControlRequestHeaders);
				_currentBits ^= 4096L;
				break;
			case 13:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.AccessControlRequestMethod, _collection._headers._AccessControlRequestMethod);
				_currentBits ^= 8192L;
				break;
			case 14:
				_current = new KeyValuePair<string, StringValues>(InternalHeaderNames.AltUsed, _collection._headers._AltUsed);
				_currentBits ^= 16384L;
				break;
			case 15:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Authorization, _collection._headers._Authorization);
				_currentBits ^= 32768L;
				break;
			case 16:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Baggage, _collection._headers._Baggage);
				_currentBits ^= 65536L;
				break;
			case 17:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.CacheControl, _collection._headers._CacheControl);
				_currentBits ^= 131072L;
				break;
			case 18:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.ContentType, _collection._headers._ContentType);
				_currentBits ^= 262144L;
				break;
			case 19:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Cookie, _collection._headers._Cookie);
				_currentBits ^= 524288L;
				break;
			case 20:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.CorrelationContext, _collection._headers._CorrelationContext);
				_currentBits ^= 1048576L;
				break;
			case 21:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Date, _collection._headers._Date);
				_currentBits ^= 2097152L;
				break;
			case 22:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Expect, _collection._headers._Expect);
				_currentBits ^= 4194304L;
				break;
			case 23:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.From, _collection._headers._From);
				_currentBits ^= 8388608L;
				break;
			case 24:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.GrpcAcceptEncoding, _collection._headers._GrpcAcceptEncoding);
				_currentBits ^= 16777216L;
				break;
			case 25:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.GrpcEncoding, _collection._headers._GrpcEncoding);
				_currentBits ^= 33554432L;
				break;
			case 26:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.GrpcTimeout, _collection._headers._GrpcTimeout);
				_currentBits ^= 67108864L;
				break;
			case 27:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.IfMatch, _collection._headers._IfMatch);
				_currentBits ^= 134217728L;
				break;
			case 28:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.IfModifiedSince, _collection._headers._IfModifiedSince);
				_currentBits ^= 268435456L;
				break;
			case 29:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.IfNoneMatch, _collection._headers._IfNoneMatch);
				_currentBits ^= 536870912L;
				break;
			case 30:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.IfRange, _collection._headers._IfRange);
				_currentBits ^= 1073741824L;
				break;
			case 31:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.IfUnmodifiedSince, _collection._headers._IfUnmodifiedSince);
				_currentBits ^= 2147483648L;
				break;
			case 32:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.KeepAlive, _collection._headers._KeepAlive);
				_currentBits ^= 4294967296L;
				break;
			case 33:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.MaxForwards, _collection._headers._MaxForwards);
				_currentBits ^= 8589934592L;
				break;
			case 34:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Origin, _collection._headers._Origin);
				_currentBits ^= 17179869184L;
				break;
			case 35:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Pragma, _collection._headers._Pragma);
				_currentBits ^= 34359738368L;
				break;
			case 36:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.ProxyAuthorization, _collection._headers._ProxyAuthorization);
				_currentBits ^= 68719476736L;
				break;
			case 37:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Range, _collection._headers._Range);
				_currentBits ^= 137438953472L;
				break;
			case 38:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Referer, _collection._headers._Referer);
				_currentBits ^= 274877906944L;
				break;
			case 39:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.RequestId, _collection._headers._RequestId);
				_currentBits ^= 549755813888L;
				break;
			case 40:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.TE, _collection._headers._TE);
				_currentBits ^= 1099511627776L;
				break;
			case 41:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.TraceParent, _collection._headers._TraceParent);
				_currentBits ^= 2199023255552L;
				break;
			case 42:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.TraceState, _collection._headers._TraceState);
				_currentBits ^= 4398046511104L;
				break;
			case 43:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.TransferEncoding, _collection._headers._TransferEncoding);
				_currentBits ^= 8796093022208L;
				break;
			case 44:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Translate, _collection._headers._Translate);
				_currentBits ^= 17592186044416L;
				break;
			case 45:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Upgrade, _collection._headers._Upgrade);
				_currentBits ^= 35184372088832L;
				break;
			case 46:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.UpgradeInsecureRequests, _collection._headers._UpgradeInsecureRequests);
				_currentBits ^= 70368744177664L;
				break;
			case 47:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Via, _collection._headers._Via);
				_currentBits ^= 140737488355328L;
				break;
			case 48:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.Warning, _collection._headers._Warning);
				_currentBits ^= 281474976710656L;
				break;
			case 49:
				_current = new KeyValuePair<string, StringValues>(HeaderNames.ContentLength, HeaderUtilities.FormatNonNegativeInt64(_collection._contentLength.GetValueOrDefault()));
				_next = -1;
				return true;
			default:
				if (!_hasUnknown || !_unknownEnumerator.MoveNext())
				{
					_current = default;
					return false;
				}
				_current = _unknownEnumerator.Current;
				return true;
			}
			if (_currentBits != 0L)
			{
				_next = BitOperations.TrailingZeroCount(_currentBits);
				return true;
			}
			_next = (_collection._contentLength.HasValue ? 49 : (-1));
			return true;
		}

		[MethodImpl(MethodImplOptions.AggressiveInlining)]
		private static int GetNext(long bits, bool hasContentLength)
		{
			if (bits == 0L)
			{
				if (!hasContentLength)
				{
					return -1;
				}
				return 49;
			}
			return BitOperations.TrailingZeroCount(bits);
		}

		internal Enumerator(HttpRequestHeaders collection)
		{
			_collection = collection;
			_currentBits = collection._bits;
			_next = GetNext(_currentBits, collection.ContentLength.HasValue);
			_current = default;
			_hasUnknown = collection.MaybeUnknown != null;
			_unknownEnumerator = (_hasUnknown ? collection.MaybeUnknown.GetEnumerator() : default(Dictionary<string, StringValues>.Enumerator));
		}

		public readonly void Dispose()
		{
		}

		public void Reset()
		{
			_currentBits = _collection._bits;
			_next = GetNext(_currentBits, _collection.ContentLength.HasValue);
		}
	}

	private sealed class EnumeratorCache
	{
		public EnumeratorBox CachedEnumerator { get; set; }

		public EnumeratorBox InUseEnumerator { get; set; }

		public void Reset()
		{
			EnumeratorBox inUseEnumerator = InUseEnumerator;
			if (inUseEnumerator != null)
			{
				InUseEnumerator = null;
				inUseEnumerator.Enumerator = default;
				CachedEnumerator = inUseEnumerator;
			}
		}
	}

	private sealed class EnumeratorBox : IEnumerator<KeyValuePair<string, StringValues>>, IEnumerator, IDisposable
	{
		public Enumerator Enumerator;

		public KeyValuePair<string, StringValues> Current => Enumerator.Current;

		object IEnumerator.Current => Current;

		public bool MoveNext()
		{
			return Enumerator.MoveNext();
		}

		public void Dispose()
		{
		}

		public void Reset()
		{
			throw new NotSupportedException();
		}
	}

	private HeaderReferences _headers;

	private EnumeratorCache _enumeratorCache;

	private long _previousBits;

	private long _pseudoBits;

	public bool HasConnection => (_bits & 2) != 0;

	public bool HasCookie => (_bits & 0x80000) != 0;

	public bool HasTransferEncoding => (_bits & 0x80000000000L) != 0;

	public int HostCount => _headers._Host.Count;

	public override StringValues HeaderConnection
	{
		get
		{
			if ((_bits & 2) != 0L)
			{
				return _headers._Connection;
			}
			return StringValues.Empty;
		}
		set
		{
			if (!StringValues.IsNullOrEmpty(value))
			{
				_bits |= 2L;
				_headers._Connection = value;
			}
			else
			{
				_bits &= -3L;
				_headers._Connection = default;
			}
		}
	}

	public StringValues HeaderHost
	{
		get
		{
			if ((_bits & 4) != 0L)
			{
				return _headers._Host;
			}
			return StringValues.Empty;
		}
		set
		{
			if (!StringValues.IsNullOrEmpty(value))
			{
				_bits |= 4L;
				_headers._Host = value;
			}
			else
			{
				_bits &= -5L;
				_headers._Host = default;
			}
		}
	}

	public StringValues HeaderAuthority
	{
		get
		{
			if ((_bits & 0x10) != 0L)
			{
				return _headers._Authority;
			}
			return StringValues.Empty;
		}
		set
		{
			if (!StringValues.IsNullOrEmpty(value))
			{
				_bits |= 16L;
				_headers._Authority = value;
			}
			else
			{
				_bits &= -17L;
				_headers._Authority = default;
			}
		}
	}

	public StringValues HeaderMethod
	{
		get
		{
			if ((_bits & 0x20) != 0L)
			{
				return _headers._Method;
			}
			return StringValues.Empty;
		}
		set
		{
			if (!StringValues.IsNullOrEmpty(value))
			{
				_bits |= 32L;
				_headers._Method = value;
			}
			else
			{
				_bits &= -33L;
				_headers._Method = default;
			}
		}
	}

	public StringValues HeaderPath
	{
		get
		{
			if ((_bits & 0x40) != 0L)
			{
				return _headers._Path;
			}
			return StringValues.Empty;
		}
		set
		{
			if (!StringValues.IsNullOrEmpty(value))
			{
				_bits |= 64L;
				_headers._Path = value;
			}
			else
			{
				_bits &= -65L;
				_headers._Path = default;
			}
		}
	}

	public StringValues HeaderProtocol
	{
		get
		{
			if ((_bits & 0x80) != 0L)
			{
				return _headers._Protocol;
			}
			return StringValues.Empty;
		}
		set
		{
			if (!StringValues.IsNullOrEmpty(value))
			{
				_bits |= 128L;
				_headers._Protocol = value;
			}
			else
			{
				_bits &= -129L;
				_headers._Protocol = default;
			}
		}
	}

	public StringValues HeaderScheme
	{
		get
		{
			if ((_bits & 0x100) != 0L)
			{
				return _headers._Scheme;
			}
			return StringValues.Empty;
		}
		set
		{
			if (!StringValues.IsNullOrEmpty(value))
			{
				_bits |= 256L;
				_headers._Scheme = value;
			}
			else
			{
				_bits &= -257L;
				_headers._Scheme = default;
			}
		}
	}

	public StringValues HeaderTransferEncoding
	{
		get
		{
			if ((_bits & 0x80000000000L) != 0L)
			{
				return _headers._TransferEncoding;
			}
			return StringValues.Empty;
		}
		set
		{
			if (!StringValues.IsNullOrEmpty(value))
			{
				_bits |= 8796093022208L;
				_headers._TransferEncoding = value;
			}
			else
			{
				_bits &= -8796093022209L;
				_headers._TransferEncoding = default;
			}
		}
	}

	public StringValues HeaderContentLength
	{
		get
		{
			if (_contentLength.HasValue)
			{
				return new StringValues(HeaderUtilities.FormatNonNegativeInt64(_contentLength.Value));
			}
			return StringValues.Empty;
		}
		set
		{
			_contentLength = ParseContentLength(value.ToString());
		}
	}

	StringValues IHeaderDictionary.Accept
	{
		get
		{
			StringValues accept = _headers._Accept;
			if ((_bits & 1) != 0L)
			{
				return accept;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 1L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Accept = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Accept = default;
			}
		}
	}

	StringValues IHeaderDictionary.Connection
	{
		get
		{
			StringValues connection = _headers._Connection;
			if ((_bits & 2) != 0L)
			{
				return connection;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 2L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Connection = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Connection = default;
			}
		}
	}

	StringValues IHeaderDictionary.Host
	{
		get
		{
			StringValues host = _headers._Host;
			if ((_bits & 4) != 0L)
			{
				return host;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 4L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Host = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Host = default;
			}
		}
	}

	StringValues IHeaderDictionary.UserAgent
	{
		get
		{
			StringValues userAgent = _headers._UserAgent;
			if ((_bits & 8) != 0L)
			{
				return userAgent;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 8L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._UserAgent = value;
			}
			else
			{
				_bits &= ~num;
				_headers._UserAgent = default;
			}
		}
	}

	StringValues IHeaderDictionary.AcceptCharset
	{
		get
		{
			StringValues acceptCharset = _headers._AcceptCharset;
			if ((_bits & 0x200) != 0L)
			{
				return acceptCharset;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 512L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._AcceptCharset = value;
			}
			else
			{
				_bits &= ~num;
				_headers._AcceptCharset = default;
			}
		}
	}

	StringValues IHeaderDictionary.AcceptEncoding
	{
		get
		{
			StringValues acceptEncoding = _headers._AcceptEncoding;
			if ((_bits & 0x400) != 0L)
			{
				return acceptEncoding;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 1024L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._AcceptEncoding = value;
			}
			else
			{
				_bits &= ~num;
				_headers._AcceptEncoding = default;
			}
		}
	}

	StringValues IHeaderDictionary.AcceptLanguage
	{
		get
		{
			StringValues acceptLanguage = _headers._AcceptLanguage;
			if ((_bits & 0x800) != 0L)
			{
				return acceptLanguage;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 2048L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._AcceptLanguage = value;
			}
			else
			{
				_bits &= ~num;
				_headers._AcceptLanguage = default;
			}
		}
	}

	StringValues IHeaderDictionary.AccessControlRequestHeaders
	{
		get
		{
			StringValues accessControlRequestHeaders = _headers._AccessControlRequestHeaders;
			if ((_bits & 0x1000) != 0L)
			{
				return accessControlRequestHeaders;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 4096L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._AccessControlRequestHeaders = value;
			}
			else
			{
				_bits &= ~num;
				_headers._AccessControlRequestHeaders = default;
			}
		}
	}

	StringValues IHeaderDictionary.AccessControlRequestMethod
	{
		get
		{
			StringValues accessControlRequestMethod = _headers._AccessControlRequestMethod;
			if ((_bits & 0x2000) != 0L)
			{
				return accessControlRequestMethod;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 8192L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._AccessControlRequestMethod = value;
			}
			else
			{
				_bits &= ~num;
				_headers._AccessControlRequestMethod = default;
			}
		}
	}

	StringValues IHeaderDictionary.Authorization
	{
		get
		{
			StringValues authorization = _headers._Authorization;
			if ((_bits & 0x8000) != 0L)
			{
				return authorization;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 32768L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Authorization = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Authorization = default;
			}
		}
	}

	StringValues IHeaderDictionary.Baggage
	{
		get
		{
			StringValues baggage = _headers._Baggage;
			if ((_bits & 0x10000) != 0L)
			{
				return baggage;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 65536L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Baggage = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Baggage = default;
			}
		}
	}

	StringValues IHeaderDictionary.CacheControl
	{
		get
		{
			StringValues cacheControl = _headers._CacheControl;
			if ((_bits & 0x20000) != 0L)
			{
				return cacheControl;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 131072L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._CacheControl = value;
			}
			else
			{
				_bits &= ~num;
				_headers._CacheControl = default;
			}
		}
	}

	StringValues IHeaderDictionary.ContentType
	{
		get
		{
			StringValues contentType = _headers._ContentType;
			if ((_bits & 0x40000) != 0L)
			{
				return contentType;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 262144L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._ContentType = value;
			}
			else
			{
				_bits &= ~num;
				_headers._ContentType = default;
			}
		}
	}

	StringValues IHeaderDictionary.Cookie
	{
		get
		{
			StringValues cookie = _headers._Cookie;
			if ((_bits & 0x80000) != 0L)
			{
				return cookie;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 524288L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Cookie = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Cookie = default;
			}
		}
	}

	StringValues IHeaderDictionary.CorrelationContext
	{
		get
		{
			StringValues correlationContext = _headers._CorrelationContext;
			if ((_bits & 0x100000) != 0L)
			{
				return correlationContext;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 1048576L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._CorrelationContext = value;
			}
			else
			{
				_bits &= ~num;
				_headers._CorrelationContext = default;
			}
		}
	}

	StringValues IHeaderDictionary.Date
	{
		get
		{
			StringValues date = _headers._Date;
			if ((_bits & 0x200000) != 0L)
			{
				return date;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 2097152L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Date = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Date = default;
			}
		}
	}

	StringValues IHeaderDictionary.Expect
	{
		get
		{
			StringValues expect = _headers._Expect;
			if ((_bits & 0x400000) != 0L)
			{
				return expect;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 4194304L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Expect = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Expect = default;
			}
		}
	}

	StringValues IHeaderDictionary.From
	{
		get
		{
			StringValues result = _headers._From;
			if ((_bits & 0x800000) != 0L)
			{
				return result;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 8388608L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._From = value;
			}
			else
			{
				_bits &= ~num;
				_headers._From = default;
			}
		}
	}

	StringValues IHeaderDictionary.GrpcAcceptEncoding
	{
		get
		{
			StringValues grpcAcceptEncoding = _headers._GrpcAcceptEncoding;
			if ((_bits & 0x1000000) != 0L)
			{
				return grpcAcceptEncoding;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 16777216L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._GrpcAcceptEncoding = value;
			}
			else
			{
				_bits &= ~num;
				_headers._GrpcAcceptEncoding = default;
			}
		}
	}

	StringValues IHeaderDictionary.GrpcEncoding
	{
		get
		{
			StringValues grpcEncoding = _headers._GrpcEncoding;
			if ((_bits & 0x2000000) != 0L)
			{
				return grpcEncoding;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 33554432L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._GrpcEncoding = value;
			}
			else
			{
				_bits &= ~num;
				_headers._GrpcEncoding = default;
			}
		}
	}

	StringValues IHeaderDictionary.GrpcTimeout
	{
		get
		{
			StringValues grpcTimeout = _headers._GrpcTimeout;
			if ((_bits & 0x4000000) != 0L)
			{
				return grpcTimeout;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 67108864L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._GrpcTimeout = value;
			}
			else
			{
				_bits &= ~num;
				_headers._GrpcTimeout = default;
			}
		}
	}

	StringValues IHeaderDictionary.IfMatch
	{
		get
		{
			StringValues ifMatch = _headers._IfMatch;
			if ((_bits & 0x8000000) != 0L)
			{
				return ifMatch;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 134217728L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._IfMatch = value;
			}
			else
			{
				_bits &= ~num;
				_headers._IfMatch = default;
			}
		}
	}

	StringValues IHeaderDictionary.IfModifiedSince
	{
		get
		{
			StringValues ifModifiedSince = _headers._IfModifiedSince;
			if ((_bits & 0x10000000) != 0L)
			{
				return ifModifiedSince;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 268435456L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._IfModifiedSince = value;
			}
			else
			{
				_bits &= ~num;
				_headers._IfModifiedSince = default;
			}
		}
	}

	StringValues IHeaderDictionary.IfNoneMatch
	{
		get
		{
			StringValues ifNoneMatch = _headers._IfNoneMatch;
			if ((_bits & 0x20000000) != 0L)
			{
				return ifNoneMatch;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 536870912L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._IfNoneMatch = value;
			}
			else
			{
				_bits &= ~num;
				_headers._IfNoneMatch = default;
			}
		}
	}

	StringValues IHeaderDictionary.IfRange
	{
		get
		{
			StringValues ifRange = _headers._IfRange;
			if ((_bits & 0x40000000) != 0L)
			{
				return ifRange;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 1073741824L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._IfRange = value;
			}
			else
			{
				_bits &= ~num;
				_headers._IfRange = default;
			}
		}
	}

	StringValues IHeaderDictionary.IfUnmodifiedSince
	{
		get
		{
			StringValues ifUnmodifiedSince = _headers._IfUnmodifiedSince;
			if ((_bits & 0x80000000u) != 0L)
			{
				return ifUnmodifiedSince;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 2147483648L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._IfUnmodifiedSince = value;
			}
			else
			{
				_bits &= ~num;
				_headers._IfUnmodifiedSince = default;
			}
		}
	}

	StringValues IHeaderDictionary.KeepAlive
	{
		get
		{
			StringValues keepAlive = _headers._KeepAlive;
			if ((_bits & 0x100000000L) != 0L)
			{
				return keepAlive;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 4294967296L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._KeepAlive = value;
			}
			else
			{
				_bits &= ~num;
				_headers._KeepAlive = default;
			}
		}
	}

	StringValues IHeaderDictionary.MaxForwards
	{
		get
		{
			StringValues maxForwards = _headers._MaxForwards;
			if ((_bits & 0x200000000L) != 0L)
			{
				return maxForwards;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 8589934592L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._MaxForwards = value;
			}
			else
			{
				_bits &= ~num;
				_headers._MaxForwards = default;
			}
		}
	}

	StringValues IHeaderDictionary.Origin
	{
		get
		{
			StringValues origin = _headers._Origin;
			if ((_bits & 0x400000000L) != 0L)
			{
				return origin;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 17179869184L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Origin = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Origin = default;
			}
		}
	}

	StringValues IHeaderDictionary.Pragma
	{
		get
		{
			StringValues pragma = _headers._Pragma;
			if ((_bits & 0x800000000L) != 0L)
			{
				return pragma;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 34359738368L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Pragma = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Pragma = default;
			}
		}
	}

	StringValues IHeaderDictionary.ProxyAuthorization
	{
		get
		{
			StringValues proxyAuthorization = _headers._ProxyAuthorization;
			if ((_bits & 0x1000000000L) != 0L)
			{
				return proxyAuthorization;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 68719476736L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._ProxyAuthorization = value;
			}
			else
			{
				_bits &= ~num;
				_headers._ProxyAuthorization = default;
			}
		}
	}

	StringValues IHeaderDictionary.Range
	{
		get
		{
			StringValues range = _headers._Range;
			if ((_bits & 0x2000000000L) != 0L)
			{
				return range;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 137438953472L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Range = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Range = default;
			}
		}
	}

	StringValues IHeaderDictionary.Referer
	{
		get
		{
			StringValues referer = _headers._Referer;
			if ((_bits & 0x4000000000L) != 0L)
			{
				return referer;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 274877906944L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Referer = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Referer = default;
			}
		}
	}

	StringValues IHeaderDictionary.RequestId
	{
		get
		{
			StringValues requestId = _headers._RequestId;
			if ((_bits & 0x8000000000L) != 0L)
			{
				return requestId;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 549755813888L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._RequestId = value;
			}
			else
			{
				_bits &= ~num;
				_headers._RequestId = default;
			}
		}
	}

	StringValues IHeaderDictionary.TE
	{
		get
		{
			StringValues tE = _headers._TE;
			if ((_bits & 0x10000000000L) != 0L)
			{
				return tE;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 1099511627776L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._TE = value;
			}
			else
			{
				_bits &= ~num;
				_headers._TE = default;
			}
		}
	}

	StringValues IHeaderDictionary.TraceParent
	{
		get
		{
			StringValues traceParent = _headers._TraceParent;
			if ((_bits & 0x20000000000L) != 0L)
			{
				return traceParent;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 2199023255552L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._TraceParent = value;
			}
			else
			{
				_bits &= ~num;
				_headers._TraceParent = default;
			}
		}
	}

	StringValues IHeaderDictionary.TraceState
	{
		get
		{
			StringValues traceState = _headers._TraceState;
			if ((_bits & 0x40000000000L) != 0L)
			{
				return traceState;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 4398046511104L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._TraceState = value;
			}
			else
			{
				_bits &= ~num;
				_headers._TraceState = default;
			}
		}
	}

	StringValues IHeaderDictionary.TransferEncoding
	{
		get
		{
			StringValues transferEncoding = _headers._TransferEncoding;
			if ((_bits & 0x80000000000L) != 0L)
			{
				return transferEncoding;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 8796093022208L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._TransferEncoding = value;
			}
			else
			{
				_bits &= ~num;
				_headers._TransferEncoding = default;
			}
		}
	}

	StringValues IHeaderDictionary.Translate
	{
		get
		{
			StringValues translate = _headers._Translate;
			if ((_bits & 0x100000000000L) != 0L)
			{
				return translate;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 17592186044416L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Translate = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Translate = default;
			}
		}
	}

	StringValues IHeaderDictionary.Upgrade
	{
		get
		{
			StringValues upgrade = _headers._Upgrade;
			if ((_bits & 0x200000000000L) != 0L)
			{
				return upgrade;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 35184372088832L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Upgrade = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Upgrade = default;
			}
		}
	}

	StringValues IHeaderDictionary.UpgradeInsecureRequests
	{
		get
		{
			StringValues upgradeInsecureRequests = _headers._UpgradeInsecureRequests;
			if ((_bits & 0x400000000000L) != 0L)
			{
				return upgradeInsecureRequests;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 70368744177664L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._UpgradeInsecureRequests = value;
			}
			else
			{
				_bits &= ~num;
				_headers._UpgradeInsecureRequests = default;
			}
		}
	}

	StringValues IHeaderDictionary.Via
	{
		get
		{
			StringValues via = _headers._Via;
			if ((_bits & 0x800000000000L) != 0L)
			{
				return via;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 140737488355328L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Via = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Via = default;
			}
		}
	}

	StringValues IHeaderDictionary.Warning
	{
		get
		{
			StringValues warning = _headers._Warning;
			if ((_bits & 0x1000000000000L) != 0L)
			{
				return warning;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			long num = 281474976710656L;
			if (value.Count > 0)
			{
				_bits |= num;
				_headers._Warning = value;
			}
			else
			{
				_bits &= ~num;
				_headers._Warning = default;
			}
		}
	}

	StringValues IHeaderDictionary.AcceptRanges
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.AcceptRanges, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.AcceptRanges, value);
		}
	}

	StringValues IHeaderDictionary.AccessControlAllowCredentials
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.AccessControlAllowCredentials, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.AccessControlAllowCredentials, value);
		}
	}

	StringValues IHeaderDictionary.AccessControlAllowHeaders
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.AccessControlAllowHeaders, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.AccessControlAllowHeaders, value);
		}
	}

	StringValues IHeaderDictionary.AccessControlAllowMethods
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.AccessControlAllowMethods, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.AccessControlAllowMethods, value);
		}
	}

	StringValues IHeaderDictionary.AccessControlAllowOrigin
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.AccessControlAllowOrigin, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.AccessControlAllowOrigin, value);
		}
	}

	StringValues IHeaderDictionary.AccessControlExposeHeaders
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.AccessControlExposeHeaders, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.AccessControlExposeHeaders, value);
		}
	}

	StringValues IHeaderDictionary.AccessControlMaxAge
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.AccessControlMaxAge, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.AccessControlMaxAge, value);
		}
	}

	StringValues IHeaderDictionary.Age
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.Age, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.Age, value);
		}
	}

	StringValues IHeaderDictionary.Allow
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.Allow, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.Allow, value);
		}
	}

	StringValues IHeaderDictionary.AltSvc
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.AltSvc, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.AltSvc, value);
		}
	}

	StringValues IHeaderDictionary.ContentDisposition
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ContentDisposition, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ContentDisposition, value);
		}
	}

	StringValues IHeaderDictionary.ContentEncoding
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ContentEncoding, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ContentEncoding, value);
		}
	}

	StringValues IHeaderDictionary.ContentLanguage
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ContentLanguage, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ContentLanguage, value);
		}
	}

	StringValues IHeaderDictionary.ContentLocation
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ContentLocation, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ContentLocation, value);
		}
	}

	StringValues IHeaderDictionary.ContentMD5
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ContentMD5, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ContentMD5, value);
		}
	}

	StringValues IHeaderDictionary.ContentRange
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ContentRange, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ContentRange, value);
		}
	}

	StringValues IHeaderDictionary.ContentSecurityPolicy
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ContentSecurityPolicy, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ContentSecurityPolicy, value);
		}
	}

	StringValues IHeaderDictionary.ContentSecurityPolicyReportOnly
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ContentSecurityPolicyReportOnly, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ContentSecurityPolicyReportOnly, value);
		}
	}

	StringValues IHeaderDictionary.ETag
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ETag, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ETag, value);
		}
	}

	StringValues IHeaderDictionary.Expires
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.Expires, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.Expires, value);
		}
	}

	StringValues IHeaderDictionary.GrpcMessage
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.GrpcMessage, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.GrpcMessage, value);
		}
	}

	StringValues IHeaderDictionary.GrpcStatus
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.GrpcStatus, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.GrpcStatus, value);
		}
	}

	StringValues IHeaderDictionary.LastModified
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.LastModified, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.LastModified, value);
		}
	}

	StringValues IHeaderDictionary.Link
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.Link, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.Link, value);
		}
	}

	StringValues IHeaderDictionary.Location
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.Location, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.Location, value);
		}
	}

	StringValues IHeaderDictionary.ProxyAuthenticate
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ProxyAuthenticate, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ProxyAuthenticate, value);
		}
	}

	StringValues IHeaderDictionary.ProxyConnection
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.ProxyConnection, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.ProxyConnection, value);
		}
	}

	StringValues IHeaderDictionary.RetryAfter
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.RetryAfter, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.RetryAfter, value);
		}
	}

	StringValues IHeaderDictionary.SecWebSocketAccept
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.SecWebSocketAccept, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.SecWebSocketAccept, value);
		}
	}

	StringValues IHeaderDictionary.SecWebSocketKey
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.SecWebSocketKey, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.SecWebSocketKey, value);
		}
	}

	StringValues IHeaderDictionary.SecWebSocketProtocol
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.SecWebSocketProtocol, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.SecWebSocketProtocol, value);
		}
	}

	StringValues IHeaderDictionary.SecWebSocketVersion
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.SecWebSocketVersion, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.SecWebSocketVersion, value);
		}
	}

	StringValues IHeaderDictionary.SecWebSocketExtensions
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.SecWebSocketExtensions, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.SecWebSocketExtensions, value);
		}
	}

	StringValues IHeaderDictionary.Server
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.Server, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.Server, value);
		}
	}

	StringValues IHeaderDictionary.SetCookie
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.SetCookie, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.SetCookie, value);
		}
	}

	StringValues IHeaderDictionary.StrictTransportSecurity
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.StrictTransportSecurity, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.StrictTransportSecurity, value);
		}
	}

	StringValues IHeaderDictionary.Trailer
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.Trailer, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.Trailer, value);
		}
	}

	StringValues IHeaderDictionary.Vary
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.Vary, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.Vary, value);
		}
	}

	StringValues IHeaderDictionary.WebSocketSubProtocols
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.WebSocketSubProtocols, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.WebSocketSubProtocols, value);
		}
	}

	StringValues IHeaderDictionary.WWWAuthenticate
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.WWWAuthenticate, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.WWWAuthenticate, value);
		}
	}

	StringValues IHeaderDictionary.XContentTypeOptions
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.XContentTypeOptions, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.XContentTypeOptions, value);
		}
	}

	StringValues IHeaderDictionary.XFrameOptions
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.XFrameOptions, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.XFrameOptions, value);
		}
	}

	StringValues IHeaderDictionary.XPoweredBy
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.XPoweredBy, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.XPoweredBy, value);
		}
	}

	StringValues IHeaderDictionary.XRequestedWith
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.XRequestedWith, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.XRequestedWith, value);
		}
	}

	StringValues IHeaderDictionary.XUACompatible
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.XUACompatible, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.XUACompatible, value);
		}
	}

	StringValues IHeaderDictionary.XXSSProtection
	{
		get
		{
			StringValues value = default;
			if (!TryGetUnknown(HeaderNames.XXSSProtection, ref value))
			{
				return StringValues.Empty;
			}
			return value;
		}
		set
		{
			if (_isReadOnly)
			{
				HttpHeaders.ThrowHeadersReadOnlyException();
			}
			SetValueUnknown(HeaderNames.XXSSProtection, value);
		}
	}

	public bool ReuseHeaderValues { get; set; }

	public Func<string, Encoding?> EncodingSelector { get; set; }

	protected override int GetCountFast()
	{
		return (_contentLength.HasValue ? 1 : 0) + BitOperations.PopCount((ulong)_bits) + (MaybeUnknown?.Count ?? 0);
	}

	protected override bool TryGetValueFast(string key, out StringValues value)
	{
		value = default;
		switch (key.Length)
		{
		case 2:
			if ((object)HeaderNames.TE == key)
			{
				if ((_bits & 0x10000000000L) != 0L)
				{
					value = _headers._TE;
					return true;
				}
				return false;
			}
			if (HeaderNames.TE.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000000000L) != 0L)
				{
					value = _headers._TE;
					return true;
				}
				return false;
			}
			break;
		case 3:
			if ((object)HeaderNames.Via == key)
			{
				if ((_bits & 0x800000000000L) != 0L)
				{
					value = _headers._Via;
					return true;
				}
				return false;
			}
			if (HeaderNames.Via.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000000000L) != 0L)
				{
					value = _headers._Via;
					return true;
				}
				return false;
			}
			break;
		case 4:
			if ((object)HeaderNames.Host == key)
			{
				if ((_bits & 4) != 0L)
				{
					value = _headers._Host;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Date == key)
			{
				if ((_bits & 0x200000) != 0L)
				{
					value = _headers._Date;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.From == key)
			{
				if ((_bits & 0x800000) != 0L)
				{
					value = _headers._From;
					return true;
				}
				return false;
			}
			if (HeaderNames.Host.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 4) != 0L)
				{
					value = _headers._Host;
					return true;
				}
				return false;
			}
			if (HeaderNames.Date.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000) != 0L)
				{
					value = _headers._Date;
					return true;
				}
				return false;
			}
			if (HeaderNames.From.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000) != 0L)
				{
					value = _headers._From;
					return true;
				}
				return false;
			}
			break;
		case 5:
			if ((object)InternalHeaderNames.Path == key)
			{
				if ((_bits & 0x40) != 0L)
				{
					value = _headers._Path;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Range == key)
			{
				if ((_bits & 0x2000000000L) != 0L)
				{
					value = _headers._Range;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Path.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40) != 0L)
				{
					value = _headers._Path;
					return true;
				}
				return false;
			}
			if (HeaderNames.Range.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000000000L) != 0L)
				{
					value = _headers._Range;
					return true;
				}
				return false;
			}
			break;
		case 6:
			if ((object)HeaderNames.Accept == key)
			{
				if ((_bits & 1) != 0L)
				{
					value = _headers._Accept;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Cookie == key)
			{
				if ((_bits & 0x80000) != 0L)
				{
					value = _headers._Cookie;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Expect == key)
			{
				if ((_bits & 0x400000) != 0L)
				{
					value = _headers._Expect;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Origin == key)
			{
				if ((_bits & 0x400000000L) != 0L)
				{
					value = _headers._Origin;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Pragma == key)
			{
				if ((_bits & 0x800000000L) != 0L)
				{
					value = _headers._Pragma;
					return true;
				}
				return false;
			}
			if (HeaderNames.Accept.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 1) != 0L)
				{
					value = _headers._Accept;
					return true;
				}
				return false;
			}
			if (HeaderNames.Cookie.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000) != 0L)
				{
					value = _headers._Cookie;
					return true;
				}
				return false;
			}
			if (HeaderNames.Expect.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000) != 0L)
				{
					value = _headers._Expect;
					return true;
				}
				return false;
			}
			if (HeaderNames.Origin.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000000L) != 0L)
				{
					value = _headers._Origin;
					return true;
				}
				return false;
			}
			if (HeaderNames.Pragma.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000000L) != 0L)
				{
					value = _headers._Pragma;
					return true;
				}
				return false;
			}
			break;
		case 7:
			if ((object)InternalHeaderNames.Method == key)
			{
				if ((_bits & 0x20) != 0L)
				{
					value = _headers._Method;
					return true;
				}
				return false;
			}
			if ((object)InternalHeaderNames.Scheme == key)
			{
				if ((_bits & 0x100) != 0L)
				{
					value = _headers._Scheme;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Baggage == key)
			{
				if ((_bits & 0x10000) != 0L)
				{
					value = _headers._Baggage;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Referer == key)
			{
				if ((_bits & 0x4000000000L) != 0L)
				{
					value = _headers._Referer;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Upgrade == key)
			{
				if ((_bits & 0x200000000000L) != 0L)
				{
					value = _headers._Upgrade;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Warning == key)
			{
				if ((_bits & 0x1000000000000L) != 0L)
				{
					value = _headers._Warning;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Method.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20) != 0L)
				{
					value = _headers._Method;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Scheme.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100) != 0L)
				{
					value = _headers._Scheme;
					return true;
				}
				return false;
			}
			if (HeaderNames.Baggage.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000) != 0L)
				{
					value = _headers._Baggage;
					return true;
				}
				return false;
			}
			if (HeaderNames.Referer.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000000000L) != 0L)
				{
					value = _headers._Referer;
					return true;
				}
				return false;
			}
			if (HeaderNames.Upgrade.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000000000L) != 0L)
				{
					value = _headers._Upgrade;
					return true;
				}
				return false;
			}
			if (HeaderNames.Warning.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000000000L) != 0L)
				{
					value = _headers._Warning;
					return true;
				}
				return false;
			}
			break;
		case 8:
			if ((object)InternalHeaderNames.AltUsed == key)
			{
				if ((_bits & 0x4000) != 0L)
				{
					value = _headers._AltUsed;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfMatch == key)
			{
				if ((_bits & 0x8000000) != 0L)
				{
					value = _headers._IfMatch;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfRange == key)
			{
				if ((_bits & 0x40000000) != 0L)
				{
					value = _headers._IfRange;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.AltUsed.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000) != 0L)
				{
					value = _headers._AltUsed;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfMatch.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000000) != 0L)
				{
					value = _headers._IfMatch;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfRange.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000000) != 0L)
				{
					value = _headers._IfRange;
					return true;
				}
				return false;
			}
			break;
		case 9:
			if ((object)InternalHeaderNames.Protocol == key)
			{
				if ((_bits & 0x80) != 0L)
				{
					value = _headers._Protocol;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Translate == key)
			{
				if ((_bits & 0x100000000000L) != 0L)
				{
					value = _headers._Translate;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Protocol.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80) != 0L)
				{
					value = _headers._Protocol;
					return true;
				}
				return false;
			}
			if (HeaderNames.Translate.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000000000L) != 0L)
				{
					value = _headers._Translate;
					return true;
				}
				return false;
			}
			break;
		case 10:
			if ((object)HeaderNames.Connection == key)
			{
				if ((_bits & 2) != 0L)
				{
					value = _headers._Connection;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.UserAgent == key)
			{
				if ((_bits & 8) != 0L)
				{
					value = _headers._UserAgent;
					return true;
				}
				return false;
			}
			if ((object)InternalHeaderNames.Authority == key)
			{
				if ((_bits & 0x10) != 0L)
				{
					value = _headers._Authority;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.KeepAlive == key)
			{
				if ((_bits & 0x100000000L) != 0L)
				{
					value = _headers._KeepAlive;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.RequestId == key)
			{
				if ((_bits & 0x8000000000L) != 0L)
				{
					value = _headers._RequestId;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.TraceState == key)
			{
				if ((_bits & 0x40000000000L) != 0L)
				{
					value = _headers._TraceState;
					return true;
				}
				return false;
			}
			if (HeaderNames.Connection.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 2) != 0L)
				{
					value = _headers._Connection;
					return true;
				}
				return false;
			}
			if (HeaderNames.UserAgent.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 8) != 0L)
				{
					value = _headers._UserAgent;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Authority.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10) != 0L)
				{
					value = _headers._Authority;
					return true;
				}
				return false;
			}
			if (HeaderNames.KeepAlive.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000000L) != 0L)
				{
					value = _headers._KeepAlive;
					return true;
				}
				return false;
			}
			if (HeaderNames.RequestId.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000000000L) != 0L)
				{
					value = _headers._RequestId;
					return true;
				}
				return false;
			}
			if (HeaderNames.TraceState.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000000000L) != 0L)
				{
					value = _headers._TraceState;
					return true;
				}
				return false;
			}
			break;
		case 11:
			if ((object)HeaderNames.TraceParent == key)
			{
				if ((_bits & 0x20000000000L) != 0L)
				{
					value = _headers._TraceParent;
					return true;
				}
				return false;
			}
			if (HeaderNames.TraceParent.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000000000L) != 0L)
				{
					value = _headers._TraceParent;
					return true;
				}
				return false;
			}
			break;
		case 12:
			if ((object)HeaderNames.ContentType == key)
			{
				if ((_bits & 0x40000) != 0L)
				{
					value = _headers._ContentType;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.GrpcTimeout == key)
			{
				if ((_bits & 0x4000000) != 0L)
				{
					value = _headers._GrpcTimeout;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.MaxForwards == key)
			{
				if ((_bits & 0x200000000L) != 0L)
				{
					value = _headers._MaxForwards;
					return true;
				}
				return false;
			}
			if (HeaderNames.ContentType.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000) != 0L)
				{
					value = _headers._ContentType;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcTimeout.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000000) != 0L)
				{
					value = _headers._GrpcTimeout;
					return true;
				}
				return false;
			}
			if (HeaderNames.MaxForwards.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000000L) != 0L)
				{
					value = _headers._MaxForwards;
					return true;
				}
				return false;
			}
			break;
		case 13:
			if ((object)HeaderNames.Authorization == key)
			{
				if ((_bits & 0x8000) != 0L)
				{
					value = _headers._Authorization;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.CacheControl == key)
			{
				if ((_bits & 0x20000) != 0L)
				{
					value = _headers._CacheControl;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.GrpcEncoding == key)
			{
				if ((_bits & 0x2000000) != 0L)
				{
					value = _headers._GrpcEncoding;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfNoneMatch == key)
			{
				if ((_bits & 0x20000000) != 0L)
				{
					value = _headers._IfNoneMatch;
					return true;
				}
				return false;
			}
			if (HeaderNames.Authorization.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000) != 0L)
				{
					value = _headers._Authorization;
					return true;
				}
				return false;
			}
			if (HeaderNames.CacheControl.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000) != 0L)
				{
					value = _headers._CacheControl;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000000) != 0L)
				{
					value = _headers._GrpcEncoding;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfNoneMatch.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000000) != 0L)
				{
					value = _headers._IfNoneMatch;
					return true;
				}
				return false;
			}
			break;
		case 14:
			if ((object)HeaderNames.AcceptCharset == key)
			{
				if ((_bits & 0x200) != 0L)
				{
					value = _headers._AcceptCharset;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.ContentLength == key)
			{
				if (_contentLength.HasValue)
				{
					value = HeaderUtilities.FormatNonNegativeInt64(_contentLength.Value);
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptCharset.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200) != 0L)
				{
					value = _headers._AcceptCharset;
					return true;
				}
				return false;
			}
			if (HeaderNames.ContentLength.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if (_contentLength.HasValue)
				{
					value = HeaderUtilities.FormatNonNegativeInt64(_contentLength.Value);
					return true;
				}
				return false;
			}
			break;
		case 15:
			if ((object)HeaderNames.AcceptEncoding == key)
			{
				if ((_bits & 0x400) != 0L)
				{
					value = _headers._AcceptEncoding;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.AcceptLanguage == key)
			{
				if ((_bits & 0x800) != 0L)
				{
					value = _headers._AcceptLanguage;
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400) != 0L)
				{
					value = _headers._AcceptEncoding;
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptLanguage.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800) != 0L)
				{
					value = _headers._AcceptLanguage;
					return true;
				}
				return false;
			}
			break;
		case 17:
			if ((object)HeaderNames.IfModifiedSince == key)
			{
				if ((_bits & 0x10000000) != 0L)
				{
					value = _headers._IfModifiedSince;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.TransferEncoding == key)
			{
				if ((_bits & 0x80000000000L) != 0L)
				{
					value = _headers._TransferEncoding;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfModifiedSince.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000000) != 0L)
				{
					value = _headers._IfModifiedSince;
					return true;
				}
				return false;
			}
			if (HeaderNames.TransferEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000000000L) != 0L)
				{
					value = _headers._TransferEncoding;
					return true;
				}
				return false;
			}
			break;
		case 19:
			if ((object)HeaderNames.CorrelationContext == key)
			{
				if ((_bits & 0x100000) != 0L)
				{
					value = _headers._CorrelationContext;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfUnmodifiedSince == key)
			{
				if ((_bits & 0x80000000u) != 0L)
				{
					value = _headers._IfUnmodifiedSince;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.ProxyAuthorization == key)
			{
				if ((_bits & 0x1000000000L) != 0L)
				{
					value = _headers._ProxyAuthorization;
					return true;
				}
				return false;
			}
			if (HeaderNames.CorrelationContext.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000) != 0L)
				{
					value = _headers._CorrelationContext;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfUnmodifiedSince.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000000u) != 0L)
				{
					value = _headers._IfUnmodifiedSince;
					return true;
				}
				return false;
			}
			if (HeaderNames.ProxyAuthorization.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000000L) != 0L)
				{
					value = _headers._ProxyAuthorization;
					return true;
				}
				return false;
			}
			break;
		case 20:
			if ((object)HeaderNames.GrpcAcceptEncoding == key)
			{
				if ((_bits & 0x1000000) != 0L)
				{
					value = _headers._GrpcAcceptEncoding;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcAcceptEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000) != 0L)
				{
					value = _headers._GrpcAcceptEncoding;
					return true;
				}
				return false;
			}
			break;
		case 25:
			if ((object)HeaderNames.UpgradeInsecureRequests == key)
			{
				if ((_bits & 0x400000000000L) != 0L)
				{
					value = _headers._UpgradeInsecureRequests;
					return true;
				}
				return false;
			}
			if (HeaderNames.UpgradeInsecureRequests.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000000000L) != 0L)
				{
					value = _headers._UpgradeInsecureRequests;
					return true;
				}
				return false;
			}
			break;
		case 29:
			if ((object)HeaderNames.AccessControlRequestMethod == key)
			{
				if ((_bits & 0x2000) != 0L)
				{
					value = _headers._AccessControlRequestMethod;
					return true;
				}
				return false;
			}
			if (HeaderNames.AccessControlRequestMethod.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000) != 0L)
				{
					value = _headers._AccessControlRequestMethod;
					return true;
				}
				return false;
			}
			break;
		case 30:
			if ((object)HeaderNames.AccessControlRequestHeaders == key)
			{
				if ((_bits & 0x1000) != 0L)
				{
					value = _headers._AccessControlRequestHeaders;
					return true;
				}
				return false;
			}
			if (HeaderNames.AccessControlRequestHeaders.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000) != 0L)
				{
					value = _headers._AccessControlRequestHeaders;
					return true;
				}
				return false;
			}
			break;
		}
		return TryGetUnknown(key, ref value);
	}

	protected override void SetValueFast(string key, StringValues value)
	{
		switch (key.Length)
		{
		case 2:
			if ((object)HeaderNames.TE == key)
			{
				_bits |= 1099511627776L;
				_headers._TE = value;
				return;
			}
			if (HeaderNames.TE.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 1099511627776L;
				_headers._TE = value;
				return;
			}
			break;
		case 3:
			if ((object)HeaderNames.Via == key)
			{
				_bits |= 140737488355328L;
				_headers._Via = value;
				return;
			}
			if (HeaderNames.Via.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 140737488355328L;
				_headers._Via = value;
				return;
			}
			break;
		case 4:
			if ((object)HeaderNames.Host == key)
			{
				_bits |= 4L;
				_headers._Host = value;
				return;
			}
			if ((object)HeaderNames.Date == key)
			{
				_bits |= 2097152L;
				_headers._Date = value;
				return;
			}
			if ((object)HeaderNames.From == key)
			{
				_bits |= 8388608L;
				_headers._From = value;
				return;
			}
			if (HeaderNames.Host.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 4L;
				_headers._Host = value;
				return;
			}
			if (HeaderNames.Date.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 2097152L;
				_headers._Date = value;
				return;
			}
			if (HeaderNames.From.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 8388608L;
				_headers._From = value;
				return;
			}
			break;
		case 5:
			if ((object)InternalHeaderNames.Path == key)
			{
				_bits |= 64L;
				_headers._Path = value;
				return;
			}
			if ((object)HeaderNames.Range == key)
			{
				_bits |= 137438953472L;
				_headers._Range = value;
				return;
			}
			if (InternalHeaderNames.Path.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 64L;
				_headers._Path = value;
				return;
			}
			if (HeaderNames.Range.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 137438953472L;
				_headers._Range = value;
				return;
			}
			break;
		case 6:
			if ((object)HeaderNames.Accept == key)
			{
				_bits |= 1L;
				_headers._Accept = value;
				return;
			}
			if ((object)HeaderNames.Cookie == key)
			{
				_bits |= 524288L;
				_headers._Cookie = value;
				return;
			}
			if ((object)HeaderNames.Expect == key)
			{
				_bits |= 4194304L;
				_headers._Expect = value;
				return;
			}
			if ((object)HeaderNames.Origin == key)
			{
				_bits |= 17179869184L;
				_headers._Origin = value;
				return;
			}
			if ((object)HeaderNames.Pragma == key)
			{
				_bits |= 34359738368L;
				_headers._Pragma = value;
				return;
			}
			if (HeaderNames.Accept.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 1L;
				_headers._Accept = value;
				return;
			}
			if (HeaderNames.Cookie.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 524288L;
				_headers._Cookie = value;
				return;
			}
			if (HeaderNames.Expect.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 4194304L;
				_headers._Expect = value;
				return;
			}
			if (HeaderNames.Origin.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 17179869184L;
				_headers._Origin = value;
				return;
			}
			if (HeaderNames.Pragma.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 34359738368L;
				_headers._Pragma = value;
				return;
			}
			break;
		case 7:
			if ((object)InternalHeaderNames.Method == key)
			{
				_bits |= 32L;
				_headers._Method = value;
				return;
			}
			if ((object)InternalHeaderNames.Scheme == key)
			{
				_bits |= 256L;
				_headers._Scheme = value;
				return;
			}
			if ((object)HeaderNames.Baggage == key)
			{
				_bits |= 65536L;
				_headers._Baggage = value;
				return;
			}
			if ((object)HeaderNames.Referer == key)
			{
				_bits |= 274877906944L;
				_headers._Referer = value;
				return;
			}
			if ((object)HeaderNames.Upgrade == key)
			{
				_bits |= 35184372088832L;
				_headers._Upgrade = value;
				return;
			}
			if ((object)HeaderNames.Warning == key)
			{
				_bits |= 281474976710656L;
				_headers._Warning = value;
				return;
			}
			if (InternalHeaderNames.Method.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 32L;
				_headers._Method = value;
				return;
			}
			if (InternalHeaderNames.Scheme.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 256L;
				_headers._Scheme = value;
				return;
			}
			if (HeaderNames.Baggage.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 65536L;
				_headers._Baggage = value;
				return;
			}
			if (HeaderNames.Referer.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 274877906944L;
				_headers._Referer = value;
				return;
			}
			if (HeaderNames.Upgrade.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 35184372088832L;
				_headers._Upgrade = value;
				return;
			}
			if (HeaderNames.Warning.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 281474976710656L;
				_headers._Warning = value;
				return;
			}
			break;
		case 8:
			if ((object)InternalHeaderNames.AltUsed == key)
			{
				_bits |= 16384L;
				_headers._AltUsed = value;
				return;
			}
			if ((object)HeaderNames.IfMatch == key)
			{
				_bits |= 134217728L;
				_headers._IfMatch = value;
				return;
			}
			if ((object)HeaderNames.IfRange == key)
			{
				_bits |= 1073741824L;
				_headers._IfRange = value;
				return;
			}
			if (InternalHeaderNames.AltUsed.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 16384L;
				_headers._AltUsed = value;
				return;
			}
			if (HeaderNames.IfMatch.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 134217728L;
				_headers._IfMatch = value;
				return;
			}
			if (HeaderNames.IfRange.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 1073741824L;
				_headers._IfRange = value;
				return;
			}
			break;
		case 9:
			if ((object)InternalHeaderNames.Protocol == key)
			{
				_bits |= 128L;
				_headers._Protocol = value;
				return;
			}
			if ((object)HeaderNames.Translate == key)
			{
				_bits |= 17592186044416L;
				_headers._Translate = value;
				return;
			}
			if (InternalHeaderNames.Protocol.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 128L;
				_headers._Protocol = value;
				return;
			}
			if (HeaderNames.Translate.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 17592186044416L;
				_headers._Translate = value;
				return;
			}
			break;
		case 10:
			if ((object)HeaderNames.Connection == key)
			{
				_bits |= 2L;
				_headers._Connection = value;
				return;
			}
			if ((object)HeaderNames.UserAgent == key)
			{
				_bits |= 8L;
				_headers._UserAgent = value;
				return;
			}
			if ((object)InternalHeaderNames.Authority == key)
			{
				_bits |= 16L;
				_headers._Authority = value;
				return;
			}
			if ((object)HeaderNames.KeepAlive == key)
			{
				_bits |= 4294967296L;
				_headers._KeepAlive = value;
				return;
			}
			if ((object)HeaderNames.RequestId == key)
			{
				_bits |= 549755813888L;
				_headers._RequestId = value;
				return;
			}
			if ((object)HeaderNames.TraceState == key)
			{
				_bits |= 4398046511104L;
				_headers._TraceState = value;
				return;
			}
			if (HeaderNames.Connection.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 2L;
				_headers._Connection = value;
				return;
			}
			if (HeaderNames.UserAgent.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 8L;
				_headers._UserAgent = value;
				return;
			}
			if (InternalHeaderNames.Authority.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 16L;
				_headers._Authority = value;
				return;
			}
			if (HeaderNames.KeepAlive.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 4294967296L;
				_headers._KeepAlive = value;
				return;
			}
			if (HeaderNames.RequestId.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 549755813888L;
				_headers._RequestId = value;
				return;
			}
			if (HeaderNames.TraceState.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 4398046511104L;
				_headers._TraceState = value;
				return;
			}
			break;
		case 11:
			if ((object)HeaderNames.TraceParent == key)
			{
				_bits |= 2199023255552L;
				_headers._TraceParent = value;
				return;
			}
			if (HeaderNames.TraceParent.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 2199023255552L;
				_headers._TraceParent = value;
				return;
			}
			break;
		case 12:
			if ((object)HeaderNames.ContentType == key)
			{
				_bits |= 262144L;
				_headers._ContentType = value;
				return;
			}
			if ((object)HeaderNames.GrpcTimeout == key)
			{
				_bits |= 67108864L;
				_headers._GrpcTimeout = value;
				return;
			}
			if ((object)HeaderNames.MaxForwards == key)
			{
				_bits |= 8589934592L;
				_headers._MaxForwards = value;
				return;
			}
			if (HeaderNames.ContentType.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 262144L;
				_headers._ContentType = value;
				return;
			}
			if (HeaderNames.GrpcTimeout.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 67108864L;
				_headers._GrpcTimeout = value;
				return;
			}
			if (HeaderNames.MaxForwards.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 8589934592L;
				_headers._MaxForwards = value;
				return;
			}
			break;
		case 13:
			if ((object)HeaderNames.Authorization == key)
			{
				_bits |= 32768L;
				_headers._Authorization = value;
				return;
			}
			if ((object)HeaderNames.CacheControl == key)
			{
				_bits |= 131072L;
				_headers._CacheControl = value;
				return;
			}
			if ((object)HeaderNames.GrpcEncoding == key)
			{
				_bits |= 33554432L;
				_headers._GrpcEncoding = value;
				return;
			}
			if ((object)HeaderNames.IfNoneMatch == key)
			{
				_bits |= 536870912L;
				_headers._IfNoneMatch = value;
				return;
			}
			if (HeaderNames.Authorization.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 32768L;
				_headers._Authorization = value;
				return;
			}
			if (HeaderNames.CacheControl.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 131072L;
				_headers._CacheControl = value;
				return;
			}
			if (HeaderNames.GrpcEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 33554432L;
				_headers._GrpcEncoding = value;
				return;
			}
			if (HeaderNames.IfNoneMatch.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 536870912L;
				_headers._IfNoneMatch = value;
				return;
			}
			break;
		case 14:
			if ((object)HeaderNames.AcceptCharset == key)
			{
				_bits |= 512L;
				_headers._AcceptCharset = value;
				return;
			}
			if ((object)HeaderNames.ContentLength == key)
			{
				_contentLength = ParseContentLength(value.ToString());
				return;
			}
			if (HeaderNames.AcceptCharset.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 512L;
				_headers._AcceptCharset = value;
				return;
			}
			if (HeaderNames.ContentLength.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_contentLength = ParseContentLength(value.ToString());
				return;
			}
			break;
		case 15:
			if ((object)HeaderNames.AcceptEncoding == key)
			{
				_bits |= 1024L;
				_headers._AcceptEncoding = value;
				return;
			}
			if ((object)HeaderNames.AcceptLanguage == key)
			{
				_bits |= 2048L;
				_headers._AcceptLanguage = value;
				return;
			}
			if (HeaderNames.AcceptEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 1024L;
				_headers._AcceptEncoding = value;
				return;
			}
			if (HeaderNames.AcceptLanguage.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 2048L;
				_headers._AcceptLanguage = value;
				return;
			}
			break;
		case 17:
			if ((object)HeaderNames.IfModifiedSince == key)
			{
				_bits |= 268435456L;
				_headers._IfModifiedSince = value;
				return;
			}
			if ((object)HeaderNames.TransferEncoding == key)
			{
				_bits |= 8796093022208L;
				_headers._TransferEncoding = value;
				return;
			}
			if (HeaderNames.IfModifiedSince.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 268435456L;
				_headers._IfModifiedSince = value;
				return;
			}
			if (HeaderNames.TransferEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 8796093022208L;
				_headers._TransferEncoding = value;
				return;
			}
			break;
		case 19:
			if ((object)HeaderNames.CorrelationContext == key)
			{
				_bits |= 1048576L;
				_headers._CorrelationContext = value;
				return;
			}
			if ((object)HeaderNames.IfUnmodifiedSince == key)
			{
				_bits |= 2147483648L;
				_headers._IfUnmodifiedSince = value;
				return;
			}
			if ((object)HeaderNames.ProxyAuthorization == key)
			{
				_bits |= 68719476736L;
				_headers._ProxyAuthorization = value;
				return;
			}
			if (HeaderNames.CorrelationContext.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 1048576L;
				_headers._CorrelationContext = value;
				return;
			}
			if (HeaderNames.IfUnmodifiedSince.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 2147483648L;
				_headers._IfUnmodifiedSince = value;
				return;
			}
			if (HeaderNames.ProxyAuthorization.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 68719476736L;
				_headers._ProxyAuthorization = value;
				return;
			}
			break;
		case 20:
			if ((object)HeaderNames.GrpcAcceptEncoding == key)
			{
				_bits |= 16777216L;
				_headers._GrpcAcceptEncoding = value;
				return;
			}
			if (HeaderNames.GrpcAcceptEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 16777216L;
				_headers._GrpcAcceptEncoding = value;
				return;
			}
			break;
		case 25:
			if ((object)HeaderNames.UpgradeInsecureRequests == key)
			{
				_bits |= 70368744177664L;
				_headers._UpgradeInsecureRequests = value;
				return;
			}
			if (HeaderNames.UpgradeInsecureRequests.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 70368744177664L;
				_headers._UpgradeInsecureRequests = value;
				return;
			}
			break;
		case 29:
			if ((object)HeaderNames.AccessControlRequestMethod == key)
			{
				_bits |= 8192L;
				_headers._AccessControlRequestMethod = value;
				return;
			}
			if (HeaderNames.AccessControlRequestMethod.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 8192L;
				_headers._AccessControlRequestMethod = value;
				return;
			}
			break;
		case 30:
			if ((object)HeaderNames.AccessControlRequestHeaders == key)
			{
				_bits |= 4096L;
				_headers._AccessControlRequestHeaders = value;
				return;
			}
			if (HeaderNames.AccessControlRequestHeaders.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				_bits |= 4096L;
				_headers._AccessControlRequestHeaders = value;
				return;
			}
			break;
		}
		SetValueUnknown(key, value);
	}

	protected override bool AddValueFast(string key, StringValues value)
	{
		switch (key.Length)
		{
		case 2:
			if ((object)HeaderNames.TE == key)
			{
				if ((_bits & 0x10000000000L) == 0L)
				{
					_bits |= 1099511627776L;
					_headers._TE = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.TE.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000000000L) == 0L)
				{
					_bits |= 1099511627776L;
					_headers._TE = value;
					return true;
				}
				return false;
			}
			break;
		case 3:
			if ((object)HeaderNames.Via == key)
			{
				if ((_bits & 0x800000000000L) == 0L)
				{
					_bits |= 140737488355328L;
					_headers._Via = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Via.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000000000L) == 0L)
				{
					_bits |= 140737488355328L;
					_headers._Via = value;
					return true;
				}
				return false;
			}
			break;
		case 4:
			if ((object)HeaderNames.Host == key)
			{
				if ((_bits & 4) == 0L)
				{
					_bits |= 4L;
					_headers._Host = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Date == key)
			{
				if ((_bits & 0x200000) == 0L)
				{
					_bits |= 2097152L;
					_headers._Date = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.From == key)
			{
				if ((_bits & 0x800000) == 0L)
				{
					_bits |= 8388608L;
					_headers._From = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Host.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 4) == 0L)
				{
					_bits |= 4L;
					_headers._Host = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Date.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000) == 0L)
				{
					_bits |= 2097152L;
					_headers._Date = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.From.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000) == 0L)
				{
					_bits |= 8388608L;
					_headers._From = value;
					return true;
				}
				return false;
			}
			break;
		case 5:
			if ((object)InternalHeaderNames.Path == key)
			{
				if ((_bits & 0x40) == 0L)
				{
					_bits |= 64L;
					_headers._Path = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Range == key)
			{
				if ((_bits & 0x2000000000L) == 0L)
				{
					_bits |= 137438953472L;
					_headers._Range = value;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Path.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40) == 0L)
				{
					_bits |= 64L;
					_headers._Path = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Range.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000000000L) == 0L)
				{
					_bits |= 137438953472L;
					_headers._Range = value;
					return true;
				}
				return false;
			}
			break;
		case 6:
			if ((object)HeaderNames.Accept == key)
			{
				if ((_bits & 1) == 0L)
				{
					_bits |= 1L;
					_headers._Accept = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Cookie == key)
			{
				if ((_bits & 0x80000) == 0L)
				{
					_bits |= 524288L;
					_headers._Cookie = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Expect == key)
			{
				if ((_bits & 0x400000) == 0L)
				{
					_bits |= 4194304L;
					_headers._Expect = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Origin == key)
			{
				if ((_bits & 0x400000000L) == 0L)
				{
					_bits |= 17179869184L;
					_headers._Origin = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Pragma == key)
			{
				if ((_bits & 0x800000000L) == 0L)
				{
					_bits |= 34359738368L;
					_headers._Pragma = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Accept.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 1) == 0L)
				{
					_bits |= 1L;
					_headers._Accept = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Cookie.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000) == 0L)
				{
					_bits |= 524288L;
					_headers._Cookie = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Expect.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000) == 0L)
				{
					_bits |= 4194304L;
					_headers._Expect = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Origin.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000000L) == 0L)
				{
					_bits |= 17179869184L;
					_headers._Origin = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Pragma.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000000L) == 0L)
				{
					_bits |= 34359738368L;
					_headers._Pragma = value;
					return true;
				}
				return false;
			}
			break;
		case 7:
			if ((object)InternalHeaderNames.Method == key)
			{
				if ((_bits & 0x20) == 0L)
				{
					_bits |= 32L;
					_headers._Method = value;
					return true;
				}
				return false;
			}
			if ((object)InternalHeaderNames.Scheme == key)
			{
				if ((_bits & 0x100) == 0L)
				{
					_bits |= 256L;
					_headers._Scheme = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Baggage == key)
			{
				if ((_bits & 0x10000) == 0L)
				{
					_bits |= 65536L;
					_headers._Baggage = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Referer == key)
			{
				if ((_bits & 0x4000000000L) == 0L)
				{
					_bits |= 274877906944L;
					_headers._Referer = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Upgrade == key)
			{
				if ((_bits & 0x200000000000L) == 0L)
				{
					_bits |= 35184372088832L;
					_headers._Upgrade = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Warning == key)
			{
				if ((_bits & 0x1000000000000L) == 0L)
				{
					_bits |= 281474976710656L;
					_headers._Warning = value;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Method.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20) == 0L)
				{
					_bits |= 32L;
					_headers._Method = value;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Scheme.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100) == 0L)
				{
					_bits |= 256L;
					_headers._Scheme = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Baggage.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000) == 0L)
				{
					_bits |= 65536L;
					_headers._Baggage = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Referer.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000000000L) == 0L)
				{
					_bits |= 274877906944L;
					_headers._Referer = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Upgrade.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000000000L) == 0L)
				{
					_bits |= 35184372088832L;
					_headers._Upgrade = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Warning.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000000000L) == 0L)
				{
					_bits |= 281474976710656L;
					_headers._Warning = value;
					return true;
				}
				return false;
			}
			break;
		case 8:
			if ((object)InternalHeaderNames.AltUsed == key)
			{
				if ((_bits & 0x4000) == 0L)
				{
					_bits |= 16384L;
					_headers._AltUsed = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfMatch == key)
			{
				if ((_bits & 0x8000000) == 0L)
				{
					_bits |= 134217728L;
					_headers._IfMatch = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfRange == key)
			{
				if ((_bits & 0x40000000) == 0L)
				{
					_bits |= 1073741824L;
					_headers._IfRange = value;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.AltUsed.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000) == 0L)
				{
					_bits |= 16384L;
					_headers._AltUsed = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfMatch.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000000) == 0L)
				{
					_bits |= 134217728L;
					_headers._IfMatch = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfRange.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000000) == 0L)
				{
					_bits |= 1073741824L;
					_headers._IfRange = value;
					return true;
				}
				return false;
			}
			break;
		case 9:
			if ((object)InternalHeaderNames.Protocol == key)
			{
				if ((_bits & 0x80) == 0L)
				{
					_bits |= 128L;
					_headers._Protocol = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Translate == key)
			{
				if ((_bits & 0x100000000000L) == 0L)
				{
					_bits |= 17592186044416L;
					_headers._Translate = value;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Protocol.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80) == 0L)
				{
					_bits |= 128L;
					_headers._Protocol = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Translate.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000000000L) == 0L)
				{
					_bits |= 17592186044416L;
					_headers._Translate = value;
					return true;
				}
				return false;
			}
			break;
		case 10:
			if ((object)HeaderNames.Connection == key)
			{
				if ((_bits & 2) == 0L)
				{
					_bits |= 2L;
					_headers._Connection = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.UserAgent == key)
			{
				if ((_bits & 8) == 0L)
				{
					_bits |= 8L;
					_headers._UserAgent = value;
					return true;
				}
				return false;
			}
			if ((object)InternalHeaderNames.Authority == key)
			{
				if ((_bits & 0x10) == 0L)
				{
					_bits |= 16L;
					_headers._Authority = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.KeepAlive == key)
			{
				if ((_bits & 0x100000000L) == 0L)
				{
					_bits |= 4294967296L;
					_headers._KeepAlive = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.RequestId == key)
			{
				if ((_bits & 0x8000000000L) == 0L)
				{
					_bits |= 549755813888L;
					_headers._RequestId = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.TraceState == key)
			{
				if ((_bits & 0x40000000000L) == 0L)
				{
					_bits |= 4398046511104L;
					_headers._TraceState = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Connection.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 2) == 0L)
				{
					_bits |= 2L;
					_headers._Connection = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.UserAgent.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 8) == 0L)
				{
					_bits |= 8L;
					_headers._UserAgent = value;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Authority.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10) == 0L)
				{
					_bits |= 16L;
					_headers._Authority = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.KeepAlive.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000000L) == 0L)
				{
					_bits |= 4294967296L;
					_headers._KeepAlive = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.RequestId.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000000000L) == 0L)
				{
					_bits |= 549755813888L;
					_headers._RequestId = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.TraceState.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000000000L) == 0L)
				{
					_bits |= 4398046511104L;
					_headers._TraceState = value;
					return true;
				}
				return false;
			}
			break;
		case 11:
			if ((object)HeaderNames.TraceParent == key)
			{
				if ((_bits & 0x20000000000L) == 0L)
				{
					_bits |= 2199023255552L;
					_headers._TraceParent = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.TraceParent.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000000000L) == 0L)
				{
					_bits |= 2199023255552L;
					_headers._TraceParent = value;
					return true;
				}
				return false;
			}
			break;
		case 12:
			if ((object)HeaderNames.ContentType == key)
			{
				if ((_bits & 0x40000) == 0L)
				{
					_bits |= 262144L;
					_headers._ContentType = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.GrpcTimeout == key)
			{
				if ((_bits & 0x4000000) == 0L)
				{
					_bits |= 67108864L;
					_headers._GrpcTimeout = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.MaxForwards == key)
			{
				if ((_bits & 0x200000000L) == 0L)
				{
					_bits |= 8589934592L;
					_headers._MaxForwards = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.ContentType.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000) == 0L)
				{
					_bits |= 262144L;
					_headers._ContentType = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcTimeout.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000000) == 0L)
				{
					_bits |= 67108864L;
					_headers._GrpcTimeout = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.MaxForwards.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000000L) == 0L)
				{
					_bits |= 8589934592L;
					_headers._MaxForwards = value;
					return true;
				}
				return false;
			}
			break;
		case 13:
			if ((object)HeaderNames.Authorization == key)
			{
				if ((_bits & 0x8000) == 0L)
				{
					_bits |= 32768L;
					_headers._Authorization = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.CacheControl == key)
			{
				if ((_bits & 0x20000) == 0L)
				{
					_bits |= 131072L;
					_headers._CacheControl = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.GrpcEncoding == key)
			{
				if ((_bits & 0x2000000) == 0L)
				{
					_bits |= 33554432L;
					_headers._GrpcEncoding = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfNoneMatch == key)
			{
				if ((_bits & 0x20000000) == 0L)
				{
					_bits |= 536870912L;
					_headers._IfNoneMatch = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.Authorization.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000) == 0L)
				{
					_bits |= 32768L;
					_headers._Authorization = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.CacheControl.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000) == 0L)
				{
					_bits |= 131072L;
					_headers._CacheControl = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000000) == 0L)
				{
					_bits |= 33554432L;
					_headers._GrpcEncoding = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfNoneMatch.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000000) == 0L)
				{
					_bits |= 536870912L;
					_headers._IfNoneMatch = value;
					return true;
				}
				return false;
			}
			break;
		case 14:
			if ((object)HeaderNames.AcceptCharset == key)
			{
				if ((_bits & 0x200) == 0L)
				{
					_bits |= 512L;
					_headers._AcceptCharset = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.ContentLength == key)
			{
				if (!_contentLength.HasValue)
				{
					_contentLength = ParseContentLength(value.ToString());
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptCharset.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200) == 0L)
				{
					_bits |= 512L;
					_headers._AcceptCharset = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.ContentLength.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if (!_contentLength.HasValue)
				{
					_contentLength = ParseContentLength(value.ToString());
					return true;
				}
				return false;
			}
			break;
		case 15:
			if ((object)HeaderNames.AcceptEncoding == key)
			{
				if ((_bits & 0x400) == 0L)
				{
					_bits |= 1024L;
					_headers._AcceptEncoding = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.AcceptLanguage == key)
			{
				if ((_bits & 0x800) == 0L)
				{
					_bits |= 2048L;
					_headers._AcceptLanguage = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400) == 0L)
				{
					_bits |= 1024L;
					_headers._AcceptEncoding = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptLanguage.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800) == 0L)
				{
					_bits |= 2048L;
					_headers._AcceptLanguage = value;
					return true;
				}
				return false;
			}
			break;
		case 17:
			if ((object)HeaderNames.IfModifiedSince == key)
			{
				if ((_bits & 0x10000000) == 0L)
				{
					_bits |= 268435456L;
					_headers._IfModifiedSince = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.TransferEncoding == key)
			{
				if ((_bits & 0x80000000000L) == 0L)
				{
					_bits |= 8796093022208L;
					_headers._TransferEncoding = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfModifiedSince.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000000) == 0L)
				{
					_bits |= 268435456L;
					_headers._IfModifiedSince = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.TransferEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000000000L) == 0L)
				{
					_bits |= 8796093022208L;
					_headers._TransferEncoding = value;
					return true;
				}
				return false;
			}
			break;
		case 19:
			if ((object)HeaderNames.CorrelationContext == key)
			{
				if ((_bits & 0x100000) == 0L)
				{
					_bits |= 1048576L;
					_headers._CorrelationContext = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfUnmodifiedSince == key)
			{
				if ((_bits & 0x80000000u) == 0L)
				{
					_bits |= 2147483648L;
					_headers._IfUnmodifiedSince = value;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.ProxyAuthorization == key)
			{
				if ((_bits & 0x1000000000L) == 0L)
				{
					_bits |= 68719476736L;
					_headers._ProxyAuthorization = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.CorrelationContext.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000) == 0L)
				{
					_bits |= 1048576L;
					_headers._CorrelationContext = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfUnmodifiedSince.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000000u) == 0L)
				{
					_bits |= 2147483648L;
					_headers._IfUnmodifiedSince = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.ProxyAuthorization.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000000L) == 0L)
				{
					_bits |= 68719476736L;
					_headers._ProxyAuthorization = value;
					return true;
				}
				return false;
			}
			break;
		case 20:
			if ((object)HeaderNames.GrpcAcceptEncoding == key)
			{
				if ((_bits & 0x1000000) == 0L)
				{
					_bits |= 16777216L;
					_headers._GrpcAcceptEncoding = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcAcceptEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000) == 0L)
				{
					_bits |= 16777216L;
					_headers._GrpcAcceptEncoding = value;
					return true;
				}
				return false;
			}
			break;
		case 25:
			if ((object)HeaderNames.UpgradeInsecureRequests == key)
			{
				if ((_bits & 0x400000000000L) == 0L)
				{
					_bits |= 70368744177664L;
					_headers._UpgradeInsecureRequests = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.UpgradeInsecureRequests.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000000000L) == 0L)
				{
					_bits |= 70368744177664L;
					_headers._UpgradeInsecureRequests = value;
					return true;
				}
				return false;
			}
			break;
		case 29:
			if ((object)HeaderNames.AccessControlRequestMethod == key)
			{
				if ((_bits & 0x2000) == 0L)
				{
					_bits |= 8192L;
					_headers._AccessControlRequestMethod = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.AccessControlRequestMethod.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000) == 0L)
				{
					_bits |= 8192L;
					_headers._AccessControlRequestMethod = value;
					return true;
				}
				return false;
			}
			break;
		case 30:
			if ((object)HeaderNames.AccessControlRequestHeaders == key)
			{
				if ((_bits & 0x1000) == 0L)
				{
					_bits |= 4096L;
					_headers._AccessControlRequestHeaders = value;
					return true;
				}
				return false;
			}
			if (HeaderNames.AccessControlRequestHeaders.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000) == 0L)
				{
					_bits |= 4096L;
					_headers._AccessControlRequestHeaders = value;
					return true;
				}
				return false;
			}
			break;
		}
		return AddValueUnknown(key, value);
	}

	protected override bool RemoveFast(string key)
	{
		switch (key.Length)
		{
		case 2:
			if ((object)HeaderNames.TE == key)
			{
				if ((_bits & 0x10000000000L) != 0L)
				{
					_bits &= -1099511627777L;
					_headers._TE = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.TE.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000000000L) != 0L)
				{
					_bits &= -1099511627777L;
					_headers._TE = default;
					return true;
				}
				return false;
			}
			break;
		case 3:
			if ((object)HeaderNames.Via == key)
			{
				if ((_bits & 0x800000000000L) != 0L)
				{
					_bits &= -140737488355329L;
					_headers._Via = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Via.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000000000L) != 0L)
				{
					_bits &= -140737488355329L;
					_headers._Via = default;
					return true;
				}
				return false;
			}
			break;
		case 4:
			if ((object)HeaderNames.Host == key)
			{
				if ((_bits & 4) != 0L)
				{
					_bits &= -5L;
					_headers._Host = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Date == key)
			{
				if ((_bits & 0x200000) != 0L)
				{
					_bits &= -2097153L;
					_headers._Date = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.From == key)
			{
				if ((_bits & 0x800000) != 0L)
				{
					_bits &= -8388609L;
					_headers._From = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Host.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 4) != 0L)
				{
					_bits &= -5L;
					_headers._Host = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Date.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000) != 0L)
				{
					_bits &= -2097153L;
					_headers._Date = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.From.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000) != 0L)
				{
					_bits &= -8388609L;
					_headers._From = default;
					return true;
				}
				return false;
			}
			break;
		case 5:
			if ((object)InternalHeaderNames.Path == key)
			{
				if ((_bits & 0x40) != 0L)
				{
					_bits &= -65L;
					_headers._Path = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Range == key)
			{
				if ((_bits & 0x2000000000L) != 0L)
				{
					_bits &= -137438953473L;
					_headers._Range = default;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Path.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40) != 0L)
				{
					_bits &= -65L;
					_headers._Path = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Range.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000000000L) != 0L)
				{
					_bits &= -137438953473L;
					_headers._Range = default;
					return true;
				}
				return false;
			}
			break;
		case 6:
			if ((object)HeaderNames.Accept == key)
			{
				if ((_bits & 1) != 0L)
				{
					_bits &= -2L;
					_headers._Accept = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Cookie == key)
			{
				if ((_bits & 0x80000) != 0L)
				{
					_bits &= -524289L;
					_headers._Cookie = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Expect == key)
			{
				if ((_bits & 0x400000) != 0L)
				{
					_bits &= -4194305L;
					_headers._Expect = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Origin == key)
			{
				if ((_bits & 0x400000000L) != 0L)
				{
					_bits &= -17179869185L;
					_headers._Origin = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Pragma == key)
			{
				if ((_bits & 0x800000000L) != 0L)
				{
					_bits &= -34359738369L;
					_headers._Pragma = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Accept.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 1) != 0L)
				{
					_bits &= -2L;
					_headers._Accept = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Cookie.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000) != 0L)
				{
					_bits &= -524289L;
					_headers._Cookie = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Expect.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000) != 0L)
				{
					_bits &= -4194305L;
					_headers._Expect = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Origin.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000000L) != 0L)
				{
					_bits &= -17179869185L;
					_headers._Origin = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Pragma.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800000000L) != 0L)
				{
					_bits &= -34359738369L;
					_headers._Pragma = default;
					return true;
				}
				return false;
			}
			break;
		case 7:
			if ((object)InternalHeaderNames.Method == key)
			{
				if ((_bits & 0x20) != 0L)
				{
					_bits &= -33L;
					_headers._Method = default;
					return true;
				}
				return false;
			}
			if ((object)InternalHeaderNames.Scheme == key)
			{
				if ((_bits & 0x100) != 0L)
				{
					_bits &= -257L;
					_headers._Scheme = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Baggage == key)
			{
				if ((_bits & 0x10000) != 0L)
				{
					_bits &= -65537L;
					_headers._Baggage = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Referer == key)
			{
				if ((_bits & 0x4000000000L) != 0L)
				{
					_bits &= -274877906945L;
					_headers._Referer = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Upgrade == key)
			{
				if ((_bits & 0x200000000000L) != 0L)
				{
					_bits &= -35184372088833L;
					_headers._Upgrade = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Warning == key)
			{
				if ((_bits & 0x1000000000000L) != 0L)
				{
					_bits &= -281474976710657L;
					_headers._Warning = default;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Method.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20) != 0L)
				{
					_bits &= -33L;
					_headers._Method = default;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Scheme.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100) != 0L)
				{
					_bits &= -257L;
					_headers._Scheme = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Baggage.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000) != 0L)
				{
					_bits &= -65537L;
					_headers._Baggage = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Referer.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000000000L) != 0L)
				{
					_bits &= -274877906945L;
					_headers._Referer = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Upgrade.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000000000L) != 0L)
				{
					_bits &= -35184372088833L;
					_headers._Upgrade = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Warning.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000000000L) != 0L)
				{
					_bits &= -281474976710657L;
					_headers._Warning = default;
					return true;
				}
				return false;
			}
			break;
		case 8:
			if ((object)InternalHeaderNames.AltUsed == key)
			{
				if ((_bits & 0x4000) != 0L)
				{
					_bits &= -16385L;
					_headers._AltUsed = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfMatch == key)
			{
				if ((_bits & 0x8000000) != 0L)
				{
					_bits &= -134217729L;
					_headers._IfMatch = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfRange == key)
			{
				if ((_bits & 0x40000000) != 0L)
				{
					_bits &= -1073741825L;
					_headers._IfRange = default;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.AltUsed.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000) != 0L)
				{
					_bits &= -16385L;
					_headers._AltUsed = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfMatch.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000000) != 0L)
				{
					_bits &= -134217729L;
					_headers._IfMatch = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfRange.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000000) != 0L)
				{
					_bits &= -1073741825L;
					_headers._IfRange = default;
					return true;
				}
				return false;
			}
			break;
		case 9:
			if ((object)InternalHeaderNames.Protocol == key)
			{
				if ((_bits & 0x80) != 0L)
				{
					_bits &= -129L;
					_headers._Protocol = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.Translate == key)
			{
				if ((_bits & 0x100000000000L) != 0L)
				{
					_bits &= -17592186044417L;
					_headers._Translate = default;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Protocol.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80) != 0L)
				{
					_bits &= -129L;
					_headers._Protocol = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Translate.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000000000L) != 0L)
				{
					_bits &= -17592186044417L;
					_headers._Translate = default;
					return true;
				}
				return false;
			}
			break;
		case 10:
			if ((object)HeaderNames.Connection == key)
			{
				if ((_bits & 2) != 0L)
				{
					_bits &= -3L;
					_headers._Connection = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.UserAgent == key)
			{
				if ((_bits & 8) != 0L)
				{
					_bits &= -9L;
					_headers._UserAgent = default;
					return true;
				}
				return false;
			}
			if ((object)InternalHeaderNames.Authority == key)
			{
				if ((_bits & 0x10) != 0L)
				{
					_bits &= -17L;
					_headers._Authority = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.KeepAlive == key)
			{
				if ((_bits & 0x100000000L) != 0L)
				{
					_bits &= -4294967297L;
					_headers._KeepAlive = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.RequestId == key)
			{
				if ((_bits & 0x8000000000L) != 0L)
				{
					_bits &= -549755813889L;
					_headers._RequestId = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.TraceState == key)
			{
				if ((_bits & 0x40000000000L) != 0L)
				{
					_bits &= -4398046511105L;
					_headers._TraceState = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Connection.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 2) != 0L)
				{
					_bits &= -3L;
					_headers._Connection = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.UserAgent.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 8) != 0L)
				{
					_bits &= -9L;
					_headers._UserAgent = default;
					return true;
				}
				return false;
			}
			if (InternalHeaderNames.Authority.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10) != 0L)
				{
					_bits &= -17L;
					_headers._Authority = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.KeepAlive.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000000L) != 0L)
				{
					_bits &= -4294967297L;
					_headers._KeepAlive = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.RequestId.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000000000L) != 0L)
				{
					_bits &= -549755813889L;
					_headers._RequestId = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.TraceState.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000000000L) != 0L)
				{
					_bits &= -4398046511105L;
					_headers._TraceState = default;
					return true;
				}
				return false;
			}
			break;
		case 11:
			if ((object)HeaderNames.TraceParent == key)
			{
				if ((_bits & 0x20000000000L) != 0L)
				{
					_bits &= -2199023255553L;
					_headers._TraceParent = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.TraceParent.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000000000L) != 0L)
				{
					_bits &= -2199023255553L;
					_headers._TraceParent = default;
					return true;
				}
				return false;
			}
			break;
		case 12:
			if ((object)HeaderNames.ContentType == key)
			{
				if ((_bits & 0x40000) != 0L)
				{
					_bits &= -262145L;
					_headers._ContentType = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.GrpcTimeout == key)
			{
				if ((_bits & 0x4000000) != 0L)
				{
					_bits &= -67108865L;
					_headers._GrpcTimeout = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.MaxForwards == key)
			{
				if ((_bits & 0x200000000L) != 0L)
				{
					_bits &= -8589934593L;
					_headers._MaxForwards = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.ContentType.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x40000) != 0L)
				{
					_bits &= -262145L;
					_headers._ContentType = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcTimeout.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x4000000) != 0L)
				{
					_bits &= -67108865L;
					_headers._GrpcTimeout = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.MaxForwards.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200000000L) != 0L)
				{
					_bits &= -8589934593L;
					_headers._MaxForwards = default;
					return true;
				}
				return false;
			}
			break;
		case 13:
			if ((object)HeaderNames.Authorization == key)
			{
				if ((_bits & 0x8000) != 0L)
				{
					_bits &= -32769L;
					_headers._Authorization = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.CacheControl == key)
			{
				if ((_bits & 0x20000) != 0L)
				{
					_bits &= -131073L;
					_headers._CacheControl = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.GrpcEncoding == key)
			{
				if ((_bits & 0x2000000) != 0L)
				{
					_bits &= -33554433L;
					_headers._GrpcEncoding = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfNoneMatch == key)
			{
				if ((_bits & 0x20000000) != 0L)
				{
					_bits &= -536870913L;
					_headers._IfNoneMatch = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.Authorization.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x8000) != 0L)
				{
					_bits &= -32769L;
					_headers._Authorization = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.CacheControl.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000) != 0L)
				{
					_bits &= -131073L;
					_headers._CacheControl = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000000) != 0L)
				{
					_bits &= -33554433L;
					_headers._GrpcEncoding = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfNoneMatch.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x20000000) != 0L)
				{
					_bits &= -536870913L;
					_headers._IfNoneMatch = default;
					return true;
				}
				return false;
			}
			break;
		case 14:
			if ((object)HeaderNames.AcceptCharset == key)
			{
				if ((_bits & 0x200) != 0L)
				{
					_bits &= -513L;
					_headers._AcceptCharset = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.ContentLength == key)
			{
				if (_contentLength.HasValue)
				{
					_contentLength = null;
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptCharset.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x200) != 0L)
				{
					_bits &= -513L;
					_headers._AcceptCharset = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.ContentLength.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if (_contentLength.HasValue)
				{
					_contentLength = null;
					return true;
				}
				return false;
			}
			break;
		case 15:
			if ((object)HeaderNames.AcceptEncoding == key)
			{
				if ((_bits & 0x400) != 0L)
				{
					_bits &= -1025L;
					_headers._AcceptEncoding = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.AcceptLanguage == key)
			{
				if ((_bits & 0x800) != 0L)
				{
					_bits &= -2049L;
					_headers._AcceptLanguage = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400) != 0L)
				{
					_bits &= -1025L;
					_headers._AcceptEncoding = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.AcceptLanguage.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x800) != 0L)
				{
					_bits &= -2049L;
					_headers._AcceptLanguage = default;
					return true;
				}
				return false;
			}
			break;
		case 17:
			if ((object)HeaderNames.IfModifiedSince == key)
			{
				if ((_bits & 0x10000000) != 0L)
				{
					_bits &= -268435457L;
					_headers._IfModifiedSince = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.TransferEncoding == key)
			{
				if ((_bits & 0x80000000000L) != 0L)
				{
					_bits &= -8796093022209L;
					_headers._TransferEncoding = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfModifiedSince.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x10000000) != 0L)
				{
					_bits &= -268435457L;
					_headers._IfModifiedSince = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.TransferEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000000000L) != 0L)
				{
					_bits &= -8796093022209L;
					_headers._TransferEncoding = default;
					return true;
				}
				return false;
			}
			break;
		case 19:
			if ((object)HeaderNames.CorrelationContext == key)
			{
				if ((_bits & 0x100000) != 0L)
				{
					_bits &= -1048577L;
					_headers._CorrelationContext = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.IfUnmodifiedSince == key)
			{
				if ((_bits & 0x80000000u) != 0L)
				{
					_bits &= -2147483649L;
					_headers._IfUnmodifiedSince = default;
					return true;
				}
				return false;
			}
			if ((object)HeaderNames.ProxyAuthorization == key)
			{
				if ((_bits & 0x1000000000L) != 0L)
				{
					_bits &= -68719476737L;
					_headers._ProxyAuthorization = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.CorrelationContext.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x100000) != 0L)
				{
					_bits &= -1048577L;
					_headers._CorrelationContext = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.IfUnmodifiedSince.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x80000000u) != 0L)
				{
					_bits &= -2147483649L;
					_headers._IfUnmodifiedSince = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.ProxyAuthorization.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000000L) != 0L)
				{
					_bits &= -68719476737L;
					_headers._ProxyAuthorization = default;
					return true;
				}
				return false;
			}
			break;
		case 20:
			if ((object)HeaderNames.GrpcAcceptEncoding == key)
			{
				if ((_bits & 0x1000000) != 0L)
				{
					_bits &= -16777217L;
					_headers._GrpcAcceptEncoding = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.GrpcAcceptEncoding.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000000) != 0L)
				{
					_bits &= -16777217L;
					_headers._GrpcAcceptEncoding = default;
					return true;
				}
				return false;
			}
			break;
		case 25:
			if ((object)HeaderNames.UpgradeInsecureRequests == key)
			{
				if ((_bits & 0x400000000000L) != 0L)
				{
					_bits &= -70368744177665L;
					_headers._UpgradeInsecureRequests = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.UpgradeInsecureRequests.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x400000000000L) != 0L)
				{
					_bits &= -70368744177665L;
					_headers._UpgradeInsecureRequests = default;
					return true;
				}
				return false;
			}
			break;
		case 29:
			if ((object)HeaderNames.AccessControlRequestMethod == key)
			{
				if ((_bits & 0x2000) != 0L)
				{
					_bits &= -8193L;
					_headers._AccessControlRequestMethod = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.AccessControlRequestMethod.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x2000) != 0L)
				{
					_bits &= -8193L;
					_headers._AccessControlRequestMethod = default;
					return true;
				}
				return false;
			}
			break;
		case 30:
			if ((object)HeaderNames.AccessControlRequestHeaders == key)
			{
				if ((_bits & 0x1000) != 0L)
				{
					_bits &= -4097L;
					_headers._AccessControlRequestHeaders = default;
					return true;
				}
				return false;
			}
			if (HeaderNames.AccessControlRequestHeaders.Equals(key, StringComparison.OrdinalIgnoreCase))
			{
				if ((_bits & 0x1000) != 0L)
				{
					_bits &= -4097L;
					_headers._AccessControlRequestHeaders = default;
					return true;
				}
				return false;
			}
			break;
		}
		return RemoveUnknown(key);
	}

	private void Clear(long bitsToClear)
	{
		long num = bitsToClear;
		if ((num & 1) != 0L)
		{
			_headers._Accept = default;
			if ((num & -2) == 0L)
			{
				return;
			}
			num &= -2;
		}
		if ((num & 2) != 0L)
		{
			_headers._Connection = default;
			if ((num & -3) == 0L)
			{
				return;
			}
			num &= -3;
		}
		if ((num & 4) != 0L)
		{
			_headers._Host = default;
			if ((num & -5) == 0L)
			{
				return;
			}
			num &= -5;
		}
		if ((num & 8) != 0L)
		{
			_headers._UserAgent = default;
			if ((num & -9) == 0L)
			{
				return;
			}
			num &= -9;
		}
		if ((num & 0x10) != 0L)
		{
			_headers._Authority = default;
			if ((num & -17) == 0L)
			{
				return;
			}
			num &= -17;
		}
		if ((num & 0x20) != 0L)
		{
			_headers._Method = default;
			if ((num & -33) == 0L)
			{
				return;
			}
			num &= -33;
		}
		if ((num & 0x40) != 0L)
		{
			_headers._Path = default;
			if ((num & -65) == 0L)
			{
				return;
			}
			num &= -65;
		}
		if ((num & 0x80) != 0L)
		{
			_headers._Protocol = default;
			if ((num & -129) == 0L)
			{
				return;
			}
			num &= -129;
		}
		if ((num & 0x100) != 0L)
		{
			_headers._Scheme = default;
			if ((num & -257) == 0L)
			{
				return;
			}
			num &= -257;
		}
		if ((num & 0x200) != 0L)
		{
			_headers._AcceptCharset = default;
			if ((num & -513) == 0L)
			{
				return;
			}
			num &= -513;
		}
		if ((num & 0x400) != 0L)
		{
			_headers._AcceptEncoding = default;
			if ((num & -1025) == 0L)
			{
				return;
			}
			num &= -1025;
		}
		if ((num & 0x800) != 0L)
		{
			_headers._AcceptLanguage = default;
			if ((num & -2049) == 0L)
			{
				return;
			}
			num &= -2049;
		}
		if ((num & 0x1000) != 0L)
		{
			_headers._AccessControlRequestHeaders = default;
			if ((num & -4097) == 0L)
			{
				return;
			}
			num &= -4097;
		}
		if ((num & 0x2000) != 0L)
		{
			_headers._AccessControlRequestMethod = default;
			if ((num & -8193) == 0L)
			{
				return;
			}
			num &= -8193;
		}
		if ((num & 0x4000) != 0L)
		{
			_headers._AltUsed = default;
			if ((num & -16385) == 0L)
			{
				return;
			}
			num &= -16385;
		}
		if ((num & 0x8000) != 0L)
		{
			_headers._Authorization = default;
			if ((num & -32769) == 0L)
			{
				return;
			}
			num &= -32769;
		}
		if ((num & 0x10000) != 0L)
		{
			_headers._Baggage = default;
			if ((num & -65537) == 0L)
			{
				return;
			}
			num &= -65537;
		}
		if ((num & 0x20000) != 0L)
		{
			_headers._CacheControl = default;
			if ((num & -131073) == 0L)
			{
				return;
			}
			num &= -131073;
		}
		if ((num & 0x40000) != 0L)
		{
			_headers._ContentType = default;
			if ((num & -262145) == 0L)
			{
				return;
			}
			num &= -262145;
		}
		if ((num & 0x80000) != 0L)
		{
			_headers._Cookie = default;
			if ((num & -524289) == 0L)
			{
				return;
			}
			num &= -524289;
		}
		if ((num & 0x100000) != 0L)
		{
			_headers._CorrelationContext = default;
			if ((num & -1048577) == 0L)
			{
				return;
			}
			num &= -1048577;
		}
		if ((num & 0x200000) != 0L)
		{
			_headers._Date = default;
			if ((num & -2097153) == 0L)
			{
				return;
			}
			num &= -2097153;
		}
		if ((num & 0x400000) != 0L)
		{
			_headers._Expect = default;
			if ((num & -4194305) == 0L)
			{
				return;
			}
			num &= -4194305;
		}
		if ((num & 0x800000) != 0L)
		{
			_headers._From = default;
			if ((num & -8388609) == 0L)
			{
				return;
			}
			num &= -8388609;
		}
		if ((num & 0x1000000) != 0L)
		{
			_headers._GrpcAcceptEncoding = default;
			if ((num & -16777217) == 0L)
			{
				return;
			}
			num &= -16777217;
		}
		if ((num & 0x2000000) != 0L)
		{
			_headers._GrpcEncoding = default;
			if ((num & -33554433) == 0L)
			{
				return;
			}
			num &= -33554433;
		}
		if ((num & 0x4000000) != 0L)
		{
			_headers._GrpcTimeout = default;
			if ((num & -67108865) == 0L)
			{
				return;
			}
			num &= -67108865;
		}
		if ((num & 0x8000000) != 0L)
		{
			_headers._IfMatch = default;
			if ((num & -134217729) == 0L)
			{
				return;
			}
			num &= -134217729;
		}
		if ((num & 0x10000000) != 0L)
		{
			_headers._IfModifiedSince = default;
			if ((num & -268435457) == 0L)
			{
				return;
			}
			num &= -268435457;
		}
		if ((num & 0x20000000) != 0L)
		{
			_headers._IfNoneMatch = default;
			if ((num & -536870913) == 0L)
			{
				return;
			}
			num &= -536870913;
		}
		if ((num & 0x40000000) != 0L)
		{
			_headers._IfRange = default;
			if ((num & -1073741825) == 0L)
			{
				return;
			}
			num &= -1073741825;
		}
		if ((num & 0x80000000u) != 0L)
		{
			_headers._IfUnmodifiedSince = default;
			if ((num & -2147483649L) == 0L)
			{
				return;
			}
			num &= -2147483649L;
		}
		if ((num & 0x100000000L) != 0L)
		{
			_headers._KeepAlive = default;
			if ((num & -4294967297L) == 0L)
			{
				return;
			}
			num &= -4294967297L;
		}
		if ((num & 0x200000000L) != 0L)
		{
			_headers._MaxForwards = default;
			if ((num & -8589934593L) == 0L)
			{
				return;
			}
			num &= -8589934593L;
		}
		if ((num & 0x400000000L) != 0L)
		{
			_headers._Origin = default;
			if ((num & -17179869185L) == 0L)
			{
				return;
			}
			num &= -17179869185L;
		}
		if ((num & 0x800000000L) != 0L)
		{
			_headers._Pragma = default;
			if ((num & -34359738369L) == 0L)
			{
				return;
			}
			num &= -34359738369L;
		}
		if ((num & 0x1000000000L) != 0L)
		{
			_headers._ProxyAuthorization = default;
			if ((num & -68719476737L) == 0L)
			{
				return;
			}
			num &= -68719476737L;
		}
		if ((num & 0x2000000000L) != 0L)
		{
			_headers._Range = default;
			if ((num & -137438953473L) == 0L)
			{
				return;
			}
			num &= -137438953473L;
		}
		if ((num & 0x4000000000L) != 0L)
		{
			_headers._Referer = default;
			if ((num & -274877906945L) == 0L)
			{
				return;
			}
			num &= -274877906945L;
		}
		if ((num & 0x8000000000L) != 0L)
		{
			_headers._RequestId = default;
			if ((num & -549755813889L) == 0L)
			{
				return;
			}
			num &= -549755813889L;
		}
		if ((num & 0x10000000000L) != 0L)
		{
			_headers._TE = default;
			if ((num & -1099511627777L) == 0L)
			{
				return;
			}
			num &= -1099511627777L;
		}
		if ((num & 0x20000000000L) != 0L)
		{
			_headers._TraceParent = default;
			if ((num & -2199023255553L) == 0L)
			{
				return;
			}
			num &= -2199023255553L;
		}
		if ((num & 0x40000000000L) != 0L)
		{
			_headers._TraceState = default;
			if ((num & -4398046511105L) == 0L)
			{
				return;
			}
			num &= -4398046511105L;
		}
		if ((num & 0x80000000000L) != 0L)
		{
			_headers._TransferEncoding = default;
			if ((num & -8796093022209L) == 0L)
			{
				return;
			}
			num &= -8796093022209L;
		}
		if ((num & 0x100000000000L) != 0L)
		{
			_headers._Translate = default;
			if ((num & -17592186044417L) == 0L)
			{
				return;
			}
			num &= -17592186044417L;
		}
		if ((num & 0x200000000000L) != 0L)
		{
			_headers._Upgrade = default;
			if ((num & -35184372088833L) == 0L)
			{
				return;
			}
			num &= -35184372088833L;
		}
		if ((num & 0x400000000000L) != 0L)
		{
			_headers._UpgradeInsecureRequests = default;
			if ((num & -70368744177665L) == 0L)
			{
				return;
			}
			num &= -70368744177665L;
		}
		if ((num & 0x800000000000L) != 0L)
		{
			_headers._Via = default;
			if ((num & -140737488355329L) == 0L)
			{
				return;
			}
			num &= -140737488355329L;
		}
		if ((num & 0x1000000000000L) != 0L)
		{
			_headers._Warning = default;
			if ((num & -281474976710657L) != 0L)
			{
				num &= -281474976710657L;
			}
		}
	}

	protected override bool CopyToFast(KeyValuePair<string, StringValues>[] array, int arrayIndex)
	{
		if (arrayIndex < 0)
		{
			return false;
		}
		if ((_bits & 1) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Accept, _headers._Accept);
			arrayIndex++;
		}
		if ((_bits & 2) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Connection, _headers._Connection);
			arrayIndex++;
		}
		if ((_bits & 4) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Host, _headers._Host);
			arrayIndex++;
		}
		if ((_bits & 8) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.UserAgent, _headers._UserAgent);
			arrayIndex++;
		}
		if ((_bits & 0x10) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(InternalHeaderNames.Authority, _headers._Authority);
			arrayIndex++;
		}
		if ((_bits & 0x20) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(InternalHeaderNames.Method, _headers._Method);
			arrayIndex++;
		}
		if ((_bits & 0x40) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(InternalHeaderNames.Path, _headers._Path);
			arrayIndex++;
		}
		if ((_bits & 0x80) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(InternalHeaderNames.Protocol, _headers._Protocol);
			arrayIndex++;
		}
		if ((_bits & 0x100) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(InternalHeaderNames.Scheme, _headers._Scheme);
			arrayIndex++;
		}
		if ((_bits & 0x200) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.AcceptCharset, _headers._AcceptCharset);
			arrayIndex++;
		}
		if ((_bits & 0x400) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.AcceptEncoding, _headers._AcceptEncoding);
			arrayIndex++;
		}
		if ((_bits & 0x800) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.AcceptLanguage, _headers._AcceptLanguage);
			arrayIndex++;
		}
		if ((_bits & 0x1000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.AccessControlRequestHeaders, _headers._AccessControlRequestHeaders);
			arrayIndex++;
		}
		if ((_bits & 0x2000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.AccessControlRequestMethod, _headers._AccessControlRequestMethod);
			arrayIndex++;
		}
		if ((_bits & 0x4000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(InternalHeaderNames.AltUsed, _headers._AltUsed);
			arrayIndex++;
		}
		if ((_bits & 0x8000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Authorization, _headers._Authorization);
			arrayIndex++;
		}
		if ((_bits & 0x10000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Baggage, _headers._Baggage);
			arrayIndex++;
		}
		if ((_bits & 0x20000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.CacheControl, _headers._CacheControl);
			arrayIndex++;
		}
		if ((_bits & 0x40000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.ContentType, _headers._ContentType);
			arrayIndex++;
		}
		if ((_bits & 0x80000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Cookie, _headers._Cookie);
			arrayIndex++;
		}
		if ((_bits & 0x100000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.CorrelationContext, _headers._CorrelationContext);
			arrayIndex++;
		}
		if ((_bits & 0x200000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Date, _headers._Date);
			arrayIndex++;
		}
		if ((_bits & 0x400000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Expect, _headers._Expect);
			arrayIndex++;
		}
		if ((_bits & 0x800000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.From, _headers._From);
			arrayIndex++;
		}
		if ((_bits & 0x1000000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.GrpcAcceptEncoding, _headers._GrpcAcceptEncoding);
			arrayIndex++;
		}
		if ((_bits & 0x2000000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.GrpcEncoding, _headers._GrpcEncoding);
			arrayIndex++;
		}
		if ((_bits & 0x4000000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.GrpcTimeout, _headers._GrpcTimeout);
			arrayIndex++;
		}
		if ((_bits & 0x8000000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.IfMatch, _headers._IfMatch);
			arrayIndex++;
		}
		if ((_bits & 0x10000000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.IfModifiedSince, _headers._IfModifiedSince);
			arrayIndex++;
		}
		if ((_bits & 0x20000000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.IfNoneMatch, _headers._IfNoneMatch);
			arrayIndex++;
		}
		if ((_bits & 0x40000000) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.IfRange, _headers._IfRange);
			arrayIndex++;
		}
		if ((_bits & 0x80000000u) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.IfUnmodifiedSince, _headers._IfUnmodifiedSince);
			arrayIndex++;
		}
		if ((_bits & 0x100000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.KeepAlive, _headers._KeepAlive);
			arrayIndex++;
		}
		if ((_bits & 0x200000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.MaxForwards, _headers._MaxForwards);
			arrayIndex++;
		}
		if ((_bits & 0x400000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Origin, _headers._Origin);
			arrayIndex++;
		}
		if ((_bits & 0x800000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Pragma, _headers._Pragma);
			arrayIndex++;
		}
		if ((_bits & 0x1000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.ProxyAuthorization, _headers._ProxyAuthorization);
			arrayIndex++;
		}
		if ((_bits & 0x2000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Range, _headers._Range);
			arrayIndex++;
		}
		if ((_bits & 0x4000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Referer, _headers._Referer);
			arrayIndex++;
		}
		if ((_bits & 0x8000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.RequestId, _headers._RequestId);
			arrayIndex++;
		}
		if ((_bits & 0x10000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.TE, _headers._TE);
			arrayIndex++;
		}
		if ((_bits & 0x20000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.TraceParent, _headers._TraceParent);
			arrayIndex++;
		}
		if ((_bits & 0x40000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.TraceState, _headers._TraceState);
			arrayIndex++;
		}
		if ((_bits & 0x80000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.TransferEncoding, _headers._TransferEncoding);
			arrayIndex++;
		}
		if ((_bits & 0x100000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Translate, _headers._Translate);
			arrayIndex++;
		}
		if ((_bits & 0x200000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Upgrade, _headers._Upgrade);
			arrayIndex++;
		}
		if ((_bits & 0x400000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.UpgradeInsecureRequests, _headers._UpgradeInsecureRequests);
			arrayIndex++;
		}
		if ((_bits & 0x800000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Via, _headers._Via);
			arrayIndex++;
		}
		if ((_bits & 0x1000000000000L) != 0L)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.Warning, _headers._Warning);
			arrayIndex++;
		}
		if (_contentLength.HasValue)
		{
			if (arrayIndex == array.Length)
			{
				return false;
			}
			array[arrayIndex] = new KeyValuePair<string, StringValues>(HeaderNames.ContentLength, HeaderUtilities.FormatNonNegativeInt64(_contentLength.Value));
			arrayIndex++;
		}
		((ICollection<KeyValuePair<string, StringValues>>)MaybeUnknown)?.CopyTo(array, arrayIndex);
		return true;
	}

	internal void ClearPseudoRequestHeaders()
	{
		_pseudoBits = _bits & 0x1F0;
		_bits &= -497L;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	internal static ushort ReadUnalignedLittleEndian_ushort(ref byte source)
	{
		ushort num = Unsafe.ReadUnaligned<ushort>(in source);
		if (!BitConverter.IsLittleEndian)
		{
			num = BinaryPrimitives.ReverseEndianness(num);
		}
		return num;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	internal static uint ReadUnalignedLittleEndian_uint(ref byte source)
	{
		uint num = Unsafe.ReadUnaligned<uint>(in source);
		if (!BitConverter.IsLittleEndian)
		{
			num = BinaryPrimitives.ReverseEndianness(num);
		}
		return num;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	internal static ulong ReadUnalignedLittleEndian_ulong(ref byte source)
	{
		ulong num = Unsafe.ReadUnaligned<ulong>(in source);
		if (!BitConverter.IsLittleEndian)
		{
			num = BinaryPrimitives.ReverseEndianness(num);
		}
		return num;
	}

	[MethodImpl(MethodImplOptions.AggressiveOptimization)]
	public void Append(ReadOnlySpan<byte> name, ReadOnlySpan<byte> value, bool checkForNewlineChars)
	{
		ref byte reference = ref MemoryMarshal.GetReference(name);
		string name2 = string.Empty;
		ref StringValues reference2 = ref Unsafe.NullRef<StringValues>();
		long num = 0L;
		switch (name.Length)
		{
		case 2:
			if ((ReadUnalignedLittleEndian_ushort(ref reference) & 0xDFDF) == 17748)
			{
				num = 1099511627776L;
				reference2 = ref _headers._TE;
				name2 = HeaderNames.TE;
			}
			break;
		case 3:
			if ((ReadUnalignedLittleEndian_ushort(ref reference) & 0xDFDF) == 18774 && (Unsafe.AddByteOffset(ref reference, (nint)2) & 0xDF) == 65)
			{
				num = 140737488355328L;
				reference2 = ref _headers._Via;
				name2 = HeaderNames.Via;
			}
			break;
		case 4:
			switch (ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFDFu)
			{
			case 1414745928u:
				num = 4L;
				reference2 = ref _headers._Host;
				name2 = HeaderNames.Host;
				break;
			case 1163149636u:
				num = 2097152L;
				reference2 = ref _headers._Date;
				name2 = HeaderNames.Date;
				break;
			case 1297044038u:
				num = 8388608L;
				reference2 = ref _headers._From;
				name2 = HeaderNames.From;
				break;
			}
			break;
		case 5:
			if ((ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFFFu) == 1413566522 && (Unsafe.AddByteOffset(ref reference, (nint)4) & 0xDF) == 72)
			{
				num = 64L;
				reference2 = ref _headers._Path;
				name2 = InternalHeaderNames.Path;
			}
			else if ((ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFDFu) == 1196310866 && (Unsafe.AddByteOffset(ref reference, (nint)4) & 0xDF) == 69)
			{
				num = 137438953472L;
				reference2 = ref _headers._Range;
				name2 = HeaderNames.Range;
			}
			break;
		case 6:
		{
			uint num3 = ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFDFu;
			if (num3 == 1162036033 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 21584)
			{
				num = 1L;
				reference2 = ref _headers._Accept;
				name2 = HeaderNames.Accept;
			}
			else if (num3 == 1263488835 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 17737)
			{
				num = 524288L;
				reference2 = ref _headers._Cookie;
				name2 = HeaderNames.Cookie;
			}
			else if (num3 == 1162893381 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 21571)
			{
				num = 4194304L;
				reference2 = ref _headers._Expect;
				name2 = HeaderNames.Expect;
			}
			else if (num3 == 1195987535 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 20041)
			{
				num = 17179869184L;
				reference2 = ref _headers._Origin;
				name2 = HeaderNames.Origin;
			}
			else if (num3 == 1195463248 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 16717)
			{
				num = 34359738368L;
				reference2 = ref _headers._Pragma;
				name2 = HeaderNames.Pragma;
			}
			break;
		}
		case 7:
			if ((ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFFFu) == 1413827898 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 20296 && (Unsafe.AddByteOffset(ref reference, (nint)6) & 0xDF) == 68)
			{
				num = 32L;
				reference2 = ref _headers._Method;
				name2 = InternalHeaderNames.Method;
			}
			else if ((ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFFFu) == 1212371770 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 19781 && (Unsafe.AddByteOffset(ref reference, (nint)6) & 0xDF) == 69)
			{
				num = 256L;
				reference2 = ref _headers._Scheme;
				name2 = InternalHeaderNames.Scheme;
			}
			else if ((ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFDFu) == 1195852098 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 18241 && (Unsafe.AddByteOffset(ref reference, (nint)6) & 0xDF) == 69)
			{
				num = 65536L;
				reference2 = ref _headers._Baggage;
				name2 = HeaderNames.Baggage;
			}
			else if ((ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFDFu) == 1162233170 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 17746 && (Unsafe.AddByteOffset(ref reference, (nint)6) & 0xDF) == 82)
			{
				num = 274877906944L;
				reference2 = ref _headers._Referer;
				name2 = HeaderNames.Referer;
			}
			else if ((ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFDFu) == 1380405333 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 17473 && (Unsafe.AddByteOffset(ref reference, (nint)6) & 0xDF) == 69)
			{
				num = 35184372088832L;
				reference2 = ref _headers._Upgrade;
				name2 = HeaderNames.Upgrade;
			}
			else if ((ReadUnalignedLittleEndian_uint(ref reference) & 0xDFDFDFDFu) == 1314013527 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)4)) & 0xDFDF) == 20041 && (Unsafe.AddByteOffset(ref reference, (nint)6) & 0xDF) == 71)
			{
				num = 281474976710656L;
				reference2 = ref _headers._Warning;
				name2 = HeaderNames.Warning;
			}
			break;
		case 8:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFFFDFDFDFuL) == 4919429793269959745L)
			{
				num = 16384L;
				reference2 = ref _headers._AltUsed;
				name2 = InternalHeaderNames.AltUsed;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFFFDFDFuL) == 5207098233614845513L)
			{
				num = 134217728L;
				reference2 = ref _headers._IfMatch;
				name2 = HeaderNames.IfMatch;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFFFDFDFuL) == 4992044754422023753L)
			{
				num = 1073741824L;
				reference2 = ref _headers._IfRange;
				name2 = HeaderNames.IfRange;
			}
			break;
		case 9:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFFFuL) == 5711495975962562618L && (Unsafe.AddByteOffset(ref reference, (nint)8) & 0xDF) == 76)
			{
				num = 128L;
				reference2 = ref _headers._Protocol;
				name2 = InternalHeaderNames.Protocol;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFDFuL) == 6071217693351039572L && (Unsafe.AddByteOffset(ref reference, (nint)8) & 0xDF) == 69)
			{
				num = 17592186044416L;
				reference2 = ref _headers._Translate;
				name2 = HeaderNames.Translate;
			}
			break;
		case 10:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFDFuL) == 5283922227757993795L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDF) == 20047)
			{
				num = 2L;
				reference2 = ref _headers._Connection;
				name2 = HeaderNames.Connection;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFFFDFDFDFDFuL) == 4992030374873092949L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDF) == 21582)
			{
				num = 8L;
				reference2 = ref _headers._UserAgent;
				name2 = HeaderNames.UserAgent;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFFFuL) == 5283372484930126138L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDF) == 22868)
			{
				num = 16L;
				reference2 = ref _headers._Authority;
				name2 = InternalHeaderNames.Authority;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFFFDFDFDFDFuL) == 5281668125874799947L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDF) == 17750)
			{
				num = 4294967296L;
				reference2 = ref _headers._KeepAlive;
				name2 = HeaderNames.KeepAlive;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xFFDFDFDFDFDFDFDFuL) == 3266327186999690578L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDF) == 17481)
			{
				num = 549755813888L;
				reference2 = ref _headers._RequestId;
				name2 = HeaderNames.RequestId;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFDFuL) == 4707479067455214164L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDF) == 17748)
			{
				num = 4398046511104L;
				reference2 = ref _headers._TraceState;
				name2 = HeaderNames.TraceState;
			}
			break;
		case 11:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFDFuL) == 5927106843007603284L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDF) == 20037 && (Unsafe.AddByteOffset(ref reference, (nint)10) & 0xDF) == 84)
			{
				num = 2199023255552L;
				reference2 = ref _headers._TraceParent;
				name2 = HeaderNames.TraceParent;
			}
			break;
		case 12:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xFFDFDFDFDFDFDFDFuL) == 3266321689424580419L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1162893652)
			{
				num = 262144L;
				reference2 = ref _headers._ContentType;
				name2 = HeaderNames.ContentType;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFFFDFDFDFDFuL) == 5569074967599927879L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1414876997)
			{
				num = 67108864L;
				reference2 = ref _headers._GrpcTimeout;
				name2 = HeaderNames.GrpcTimeout;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFFFDFDFDFuL) == 6292178792217067853L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1396986433)
			{
				num = 8589934592L;
				reference2 = ref _headers._MaxForwards;
				name2 = HeaderNames.MaxForwards;
			}
			break;
		case 13:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFDFuL) == 6505821637182772545L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1330205761 && (Unsafe.AddByteOffset(ref reference, (nint)12) & 0xDF) == 78)
			{
				num = 32768L;
				reference2 = ref _headers._Authorization;
				name2 = HeaderNames.Authorization;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFFFDFDFDFDFDFuL) == 5711458528024281411L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1330795598 && (Unsafe.AddByteOffset(ref reference, (nint)12) & 0xDF) == 76)
			{
				num = 131072L;
				reference2 = ref _headers._CacheControl;
				name2 = HeaderNames.CacheControl;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFFFDFDFDFDFuL) == 4849889909429785159L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1313424463 && (Unsafe.AddByteOffset(ref reference, (nint)12) & 0xDF) == 71)
			{
				num = 33554432L;
				reference2 = ref _headers._GrpcEncoding;
				name2 = HeaderNames.GrpcEncoding;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xFFDFDFDFDFFFDFDFuL) == 3262099607620765257L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1129595213 && (Unsafe.AddByteOffset(ref reference, (nint)12) & 0xDF) == 72)
			{
				num = 536870912L;
				reference2 = ref _headers._IfNoneMatch;
				name2 = HeaderNames.IfNoneMatch;
			}
			break;
		case 14:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFFFDFDFDFDFDFDFuL) == 4840617878229304129L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1397899592 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)12)) & 0xDFDF) == 21573)
			{
				num = 512L;
				reference2 = ref _headers._AcceptCharset;
				name2 = HeaderNames.AcceptCharset;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xFFDFDFDFDFDFDFDFuL) == 3266321689424580419L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1196311884 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)12)) & 0xDFDF) == 18516)
			{
				Encoding encoding = (((object)EncodingSelector == KestrelServerOptions.DefaultHeaderEncodingSelector) ? null : EncodingSelector(HeaderNames.ContentLength));
				if (encoding == null)
				{
					AppendContentLength(value);
				}
				else
				{
					AppendContentLengthCustomEncoding(value, encoding);
				}
				return;
			}
			break;
		case 15:
		{
			ulong num2 = ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFFFDFDFDFDFDFDFuL;
			if (num2 == 4984733066305160001L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1146045262 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)12)) & 0xDFDF) == 20041 && (Unsafe.AddByteOffset(ref reference, (nint)14) & 0xDF) == 71)
			{
				num = 1024L;
				reference2 = ref _headers._AcceptEncoding;
				name2 = HeaderNames.AcceptEncoding;
			}
			else if (num2 == 5489136224570655553L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFu) == 1430736449 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)12)) & 0xDFDF) == 18241 && (Unsafe.AddByteOffset(ref reference, (nint)14) & 0xDF) == 69)
			{
				num = 2048L;
				reference2 = ref _headers._AcceptLanguage;
				name2 = HeaderNames.AcceptLanguage;
			}
			break;
		}
		case 17:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFFFDFDFuL) == 5064654363342751305L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFFFDFDFDFuL) == 4849894470315165001L && (Unsafe.AddByteOffset(ref reference, (nint)16) & 0xDF) == 69)
			{
				num = 268435456L;
				reference2 = ref _headers._IfModifiedSince;
				name2 = HeaderNames.IfModifiedSince;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFDFuL) == 5928221808112259668L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFDFDFDFFFuL) == 5641115115480565037L && (Unsafe.AddByteOffset(ref reference, (nint)16) & 0xDF) == 71)
			{
				num = 8796093022208L;
				reference2 = ref _headers._TransferEncoding;
				name2 = HeaderNames.TransferEncoding;
			}
			break;
		case 19:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFDFDFDFuL) == 6071217633289719619L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFFFDFDFDFuL) == 6074880097310887753L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)16)) & 0xDFDF) == 22597 && (Unsafe.AddByteOffset(ref reference, (nint)18) & 0xDF) == 84)
			{
				num = 1048576L;
				reference2 = ref _headers._CorrelationContext;
				name2 = HeaderNames.CorrelationContext;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFDFDFFFDFDFuL) == 4922237916571059785L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFFFDFDFDFDFDFuL) == 5283616559079179849L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)16)) & 0xDFDF) == 17230 && (Unsafe.AddByteOffset(ref reference, (nint)18) & 0xDF) == 69)
			{
				num = 2147483648L;
				reference2 = ref _headers._IfUnmodifiedSince;
				name2 = HeaderNames.IfUnmodifiedSince;
			}
			else if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFFFDFDFDFDFDFuL) == 6143241228466999888L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFDFDFDFDFuL) == 6071233043632179284L && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)16)) & 0xDFDF) == 20297 && (Unsafe.AddByteOffset(ref reference, (nint)18) & 0xDF) == 78)
			{
				num = 68719476736L;
				reference2 = ref _headers._ProxyAuthorization;
				name2 = HeaderNames.ProxyAuthorization;
			}
			break;
		case 20:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFDFDFFFDFDFDFDFuL) == 4846789286639456839L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFFFDFDFDFuL) == 5711494811456131141L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)16)) & 0xDFDFDFDFu) == 1196312900)
			{
				num = 16777216L;
				reference2 = ref _headers._GrpcAcceptEncoding;
				name2 = HeaderNames.GrpcAcceptEncoding;
			}
			break;
		case 25:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xFFDFDFDFDFDFDFDFuL) == 3262088552443760725L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFDFDFDFDFDFDFDFuL) == 4995148684121558601L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)16)) & 0xDFDFDFDFDFDFDFFFuL) == 6076276554990965293L && (Unsafe.AddByteOffset(ref reference, (nint)24) & 0xDF) == 83)
			{
				num = 70368744177664L;
				reference2 = ref _headers._UpgradeInsecureRequests;
				name2 = HeaderNames.UpgradeInsecureRequests;
			}
			break;
		case 29:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFFFDFDFDFDFDFDFuL) == 4840616791602578241L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFFFDFDFDFDFDFDFuL) == 5921472988629454415L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)16)) & 0xDFFFDFDFDFDFDFDFuL) == 5561193831494668613L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)24)) & 0xDFDFDFDFu) == 1330140229 && (Unsafe.AddByteOffset(ref reference, (nint)28) & 0xDF) == 68)
			{
				num = 8192L;
				reference2 = ref _headers._AccessControlRequestMethod;
				name2 = HeaderNames.AccessControlRequestMethod;
			}
			break;
		case 30:
			if ((ReadUnalignedLittleEndian_ulong(ref reference) & 0xDFFFDFDFDFDFDFDFuL) == 4840616791602578241L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)8)) & 0xDFFFDFDFDFDFDFDFuL) == 5921472988629454415L && (ReadUnalignedLittleEndian_ulong(ref Unsafe.AddByteOffset(ref reference, (nint)16)) & 0xDFFFDFDFDFDFDFDFuL) == 5200905861305028933L && (ReadUnalignedLittleEndian_uint(ref Unsafe.AddByteOffset(ref reference, (nint)24)) & 0xDFDFDFDFu) == 1162101061 && (ReadUnalignedLittleEndian_ushort(ref Unsafe.AddByteOffset(ref reference, (nint)28)) & 0xDFDF) == 21330)
			{
				num = 4096L;
				reference2 = ref _headers._AccessControlRequestHeaders;
				name2 = HeaderNames.AccessControlRequestHeaders;
			}
			break;
		}
		if (num != 0L)
		{
			if ((_previousBits & num) != 0L)
			{
				_previousBits ^= num;
				if (reference2.Count == 1)
				{
					string text = reference2.ToString();
					if (text.Length == value.Length && StringUtilities.BytesOrdinalEqualsStringAndAscii(text, value))
					{
						_bits |= num;
						return;
					}
				}
			}
			string requestHeaderString = value.GetRequestHeaderString(name2, EncodingSelector, checkForNewlineChars);
			if ((_bits & num) == 0L)
			{
				_bits |= num;
				reference2 = new StringValues(requestHeaderString);
			}
			else
			{
				reference2 = HttpHeaders.AppendValue(reference2, requestHeaderString);
			}
		}
		else
		{
			name2 = name.GetHeaderName();
			string requestHeaderString2 = value.GetRequestHeaderString(name2, EncodingSelector, checkForNewlineChars);
			AppendUnknownHeaders(name2, requestHeaderString2);
		}
	}

	[MethodImpl(MethodImplOptions.AggressiveOptimization)]
	public bool TryHPackAppend(int index, ReadOnlySpan<byte> value, bool checkForNewlineChars)
	{
		ref StringValues reference = ref Unsafe.NullRef<StringValues>();
		string name = string.Empty;
		long num = 0L;
		switch (index)
		{
		case 1:
			num = 16L;
			reference = ref _headers._Authority;
			name = InternalHeaderNames.Authority;
			break;
		case 2:
		case 3:
			num = 32L;
			reference = ref _headers._Method;
			name = InternalHeaderNames.Method;
			break;
		case 4:
		case 5:
			num = 64L;
			reference = ref _headers._Path;
			name = InternalHeaderNames.Path;
			break;
		case 6:
		case 7:
			num = 256L;
			reference = ref _headers._Scheme;
			name = InternalHeaderNames.Scheme;
			break;
		case 15:
			num = 512L;
			reference = ref _headers._AcceptCharset;
			name = HeaderNames.AcceptCharset;
			break;
		case 16:
			num = 1024L;
			reference = ref _headers._AcceptEncoding;
			name = HeaderNames.AcceptEncoding;
			break;
		case 17:
			num = 2048L;
			reference = ref _headers._AcceptLanguage;
			name = HeaderNames.AcceptLanguage;
			break;
		case 19:
			num = 1L;
			reference = ref _headers._Accept;
			name = HeaderNames.Accept;
			break;
		case 23:
			num = 32768L;
			reference = ref _headers._Authorization;
			name = HeaderNames.Authorization;
			break;
		case 24:
			num = 131072L;
			reference = ref _headers._CacheControl;
			name = HeaderNames.CacheControl;
			break;
		case 28:
		{
			Encoding encoding = (((object)EncodingSelector == KestrelServerOptions.DefaultHeaderEncodingSelector) ? null : EncodingSelector(HeaderNames.ContentLength));
			if (encoding == null)
			{
				AppendContentLength(value);
			}
			else
			{
				AppendContentLengthCustomEncoding(value, encoding);
			}
			return true;
		}
		case 31:
			num = 262144L;
			reference = ref _headers._ContentType;
			name = HeaderNames.ContentType;
			break;
		case 32:
			num = 524288L;
			reference = ref _headers._Cookie;
			name = HeaderNames.Cookie;
			break;
		case 33:
			num = 2097152L;
			reference = ref _headers._Date;
			name = HeaderNames.Date;
			break;
		case 35:
			num = 4194304L;
			reference = ref _headers._Expect;
			name = HeaderNames.Expect;
			break;
		case 37:
			num = 8388608L;
			reference = ref _headers._From;
			name = HeaderNames.From;
			break;
		case 38:
			num = 4L;
			reference = ref _headers._Host;
			name = HeaderNames.Host;
			break;
		case 39:
			num = 134217728L;
			reference = ref _headers._IfMatch;
			name = HeaderNames.IfMatch;
			break;
		case 40:
			num = 268435456L;
			reference = ref _headers._IfModifiedSince;
			name = HeaderNames.IfModifiedSince;
			break;
		case 41:
			num = 536870912L;
			reference = ref _headers._IfNoneMatch;
			name = HeaderNames.IfNoneMatch;
			break;
		case 42:
			num = 1073741824L;
			reference = ref _headers._IfRange;
			name = HeaderNames.IfRange;
			break;
		case 43:
			num = 2147483648L;
			reference = ref _headers._IfUnmodifiedSince;
			name = HeaderNames.IfUnmodifiedSince;
			break;
		case 47:
			num = 8589934592L;
			reference = ref _headers._MaxForwards;
			name = HeaderNames.MaxForwards;
			break;
		case 49:
			num = 68719476736L;
			reference = ref _headers._ProxyAuthorization;
			name = HeaderNames.ProxyAuthorization;
			break;
		case 50:
			num = 137438953472L;
			reference = ref _headers._Range;
			name = HeaderNames.Range;
			break;
		case 51:
			num = 274877906944L;
			reference = ref _headers._Referer;
			name = HeaderNames.Referer;
			break;
		case 57:
			num = 8796093022208L;
			reference = ref _headers._TransferEncoding;
			name = HeaderNames.TransferEncoding;
			break;
		case 58:
			num = 8L;
			reference = ref _headers._UserAgent;
			name = HeaderNames.UserAgent;
			break;
		case 60:
			num = 140737488355328L;
			reference = ref _headers._Via;
			name = HeaderNames.Via;
			break;
		}
		if (num != 0L)
		{
			if ((_previousBits & num) != 0L)
			{
				_previousBits ^= num;
				if (reference.Count == 1)
				{
					string text = reference.ToString();
					if (text.Length == value.Length && StringUtilities.BytesOrdinalEqualsStringAndAscii(text, value))
					{
						_bits |= num;
						return true;
					}
				}
			}
			string requestHeaderString = value.GetRequestHeaderString(name, EncodingSelector, checkForNewlineChars);
			if ((_bits & num) == 0L)
			{
				_bits |= num;
				reference = new StringValues(requestHeaderString);
			}
			else
			{
				reference = HttpHeaders.AppendValue(reference, requestHeaderString);
			}
			return true;
		}
		return false;
	}

	[MethodImpl(MethodImplOptions.AggressiveOptimization)]
	public bool TryQPackAppend(int index, ReadOnlySpan<byte> value, bool checkForNewlineChars)
	{
		ref StringValues reference = ref Unsafe.NullRef<StringValues>();
		string name = string.Empty;
		long num = 0L;
		switch (index)
		{
		case 0:
			num = 16L;
			reference = ref _headers._Authority;
			name = InternalHeaderNames.Authority;
			break;
		case 1:
			num = 64L;
			reference = ref _headers._Path;
			name = InternalHeaderNames.Path;
			break;
		case 4:
		{
			Encoding encoding = (((object)EncodingSelector == KestrelServerOptions.DefaultHeaderEncodingSelector) ? null : EncodingSelector(HeaderNames.ContentLength));
			if (encoding == null)
			{
				AppendContentLength(value);
			}
			else
			{
				AppendContentLengthCustomEncoding(value, encoding);
			}
			return true;
		}
		case 5:
			num = 524288L;
			reference = ref _headers._Cookie;
			name = HeaderNames.Cookie;
			break;
		case 6:
			num = 2097152L;
			reference = ref _headers._Date;
			name = HeaderNames.Date;
			break;
		case 8:
			num = 268435456L;
			reference = ref _headers._IfModifiedSince;
			name = HeaderNames.IfModifiedSince;
			break;
		case 9:
			num = 536870912L;
			reference = ref _headers._IfNoneMatch;
			name = HeaderNames.IfNoneMatch;
			break;
		case 13:
			num = 274877906944L;
			reference = ref _headers._Referer;
			name = HeaderNames.Referer;
			break;
		case 15:
		case 16:
		case 17:
		case 18:
		case 19:
		case 20:
		case 21:
			num = 32L;
			reference = ref _headers._Method;
			name = InternalHeaderNames.Method;
			break;
		case 22:
		case 23:
			num = 256L;
			reference = ref _headers._Scheme;
			name = InternalHeaderNames.Scheme;
			break;
		case 29:
		case 30:
			num = 1L;
			reference = ref _headers._Accept;
			name = HeaderNames.Accept;
			break;
		case 31:
			num = 1024L;
			reference = ref _headers._AcceptEncoding;
			name = HeaderNames.AcceptEncoding;
			break;
		case 36:
		case 37:
		case 38:
		case 39:
		case 40:
		case 41:
			num = 131072L;
			reference = ref _headers._CacheControl;
			name = HeaderNames.CacheControl;
			break;
		case 44:
		case 45:
		case 46:
		case 47:
		case 48:
		case 49:
		case 50:
		case 51:
		case 52:
		case 53:
		case 54:
			num = 262144L;
			reference = ref _headers._ContentType;
			name = HeaderNames.ContentType;
			break;
		case 55:
			num = 137438953472L;
			reference = ref _headers._Range;
			name = HeaderNames.Range;
			break;
		case 72:
			num = 2048L;
			reference = ref _headers._AcceptLanguage;
			name = HeaderNames.AcceptLanguage;
			break;
		case 80:
			num = 4096L;
			reference = ref _headers._AccessControlRequestHeaders;
			name = HeaderNames.AccessControlRequestHeaders;
			break;
		case 81:
		case 82:
			num = 8192L;
			reference = ref _headers._AccessControlRequestMethod;
			name = HeaderNames.AccessControlRequestMethod;
			break;
		case 84:
			num = 32768L;
			reference = ref _headers._Authorization;
			name = HeaderNames.Authorization;
			break;
		case 89:
			num = 1073741824L;
			reference = ref _headers._IfRange;
			name = HeaderNames.IfRange;
			break;
		case 90:
			num = 17179869184L;
			reference = ref _headers._Origin;
			name = HeaderNames.Origin;
			break;
		case 94:
			num = 70368744177664L;
			reference = ref _headers._UpgradeInsecureRequests;
			name = HeaderNames.UpgradeInsecureRequests;
			break;
		case 95:
			num = 8L;
			reference = ref _headers._UserAgent;
			name = HeaderNames.UserAgent;
			break;
		}
		if (num != 0L)
		{
			if ((_previousBits & num) != 0L)
			{
				_previousBits ^= num;
				if (reference.Count == 1)
				{
					string text = reference.ToString();
					if (text.Length == value.Length && StringUtilities.BytesOrdinalEqualsStringAndAscii(text, value))
					{
						_bits |= num;
						return true;
					}
				}
			}
			string requestHeaderString = value.GetRequestHeaderString(name, EncodingSelector, checkForNewlineChars);
			if ((_bits & num) == 0L)
			{
				_bits |= num;
				reference = new StringValues(requestHeaderString);
			}
			else
			{
				reference = HttpHeaders.AppendValue(reference, requestHeaderString);
			}
			return true;
		}
		return false;
	}

	public HttpRequestHeaders(bool reuseHeaderValues = true, Func<string, Encoding?>? encodingSelector = null)
	{
		ReuseHeaderValues = reuseHeaderValues;
		EncodingSelector = encodingSelector ?? KestrelServerOptions.DefaultHeaderEncodingSelector;
	}

	public void OnHeadersComplete()
	{
		long bits = _bits;
		long previousBits = _previousBits;
		_previousBits = 0L;
		long num = ~bits & previousBits;
		if (num != 0L)
		{
			Clear(num);
		}
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	public void MergeCookies()
	{
		if (HasCookie && _headers._Cookie.Count > 1)
		{
			_headers._Cookie = string.Join("; ", _headers._Cookie.ToArray());
		}
	}

	protected override void ClearFast()
	{
		if (!ReuseHeaderValues)
		{
			Clear(_bits | _pseudoBits);
		}
		else
		{
			_previousBits = _bits | _pseudoBits;
		}
		_bits = 0L;
		_pseudoBits = 0L;
		_contentLength = null;
		MaybeUnknown?.Clear();
		_enumeratorCache?.Reset();
	}

	private static long ParseContentLength(string value)
	{
		if (!HeaderUtilities.TryParseNonNegativeInt64(value, out var result))
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidContentLength, value);
		}
		return result;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private void AppendContentLength(ReadOnlySpan<byte> value)
	{
		if (_contentLength.HasValue)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.MultipleContentLengths);
		}
		if (!Utf8Parser.TryParse(value, out long value2, out int bytesConsumed, '\0') || value2 < 0 || bytesConsumed != value.Length)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidContentLength, value.GetRequestHeaderString(HeaderNames.ContentLength, EncodingSelector, checkForNewlineChars: false));
		}
		_contentLength = value2;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	[SkipLocalsInit]
	private void AppendContentLengthCustomEncoding(ReadOnlySpan<byte> value, Encoding customEncoding)
	{
		if (_contentLength.HasValue)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.MultipleContentLengths);
		}
		Span<char> chars = stackalloc char[20];
		int chars2 = customEncoding.GetChars(value, chars);
		long result = -1L;
		if (chars2 > 19 || !long.TryParse(chars.Slice(0, chars2), NumberStyles.Integer, CultureInfo.InvariantCulture, out result) || result < 0)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidContentLength, value.GetRequestHeaderString(HeaderNames.ContentLength, EncodingSelector, checkForNewlineChars: false));
		}
		_contentLength = result;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private void SetValueUnknown(string key, StringValues value)
	{
		Unknown[HttpHeaders.GetInternedHeaderName(key)] = value;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private bool AddValueUnknown(string key, StringValues value)
	{
		Unknown.Add(HttpHeaders.GetInternedHeaderName(key), value);
		return true;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private void AppendUnknownHeaders(string name, string valueString)
	{
		name = HttpHeaders.GetInternedHeaderName(name);
		Unknown.TryGetValue(name, out var value);
		Unknown[name] = HttpHeaders.AppendValue(value, valueString);
	}

	public Enumerator GetEnumerator()
	{
		return new Enumerator(this);
	}

	protected override IEnumerator<KeyValuePair<string, StringValues>> GetEnumeratorFast()
	{
		EnumeratorCache enumeratorCache = _enumeratorCache ?? (_enumeratorCache = new EnumeratorCache());
		EnumeratorBox enumeratorBox2;
		if (enumeratorCache.CachedEnumerator != null)
		{
			EnumeratorBox enumeratorBox = (enumeratorCache.InUseEnumerator = enumeratorCache.CachedEnumerator);
			enumeratorBox2 = enumeratorBox;
			enumeratorCache.CachedEnumerator = null;
		}
		else
		{
			EnumeratorBox enumeratorBox = (enumeratorCache.InUseEnumerator = new EnumeratorBox());
			enumeratorBox2 = enumeratorBox;
		}
		enumeratorBox2.Enumerator = new Enumerator(this);
		return enumeratorBox2;
	}
}
