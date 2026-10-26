using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Shared;
using Microsoft.Extensions.Primitives;
using Microsoft.Net.Http.Headers;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;

[DebuggerDisplay("{DebuggerToString(),nq}")]
[DebuggerTypeProxy(typeof(StringValuesDictionaryDebugView))]
internal abstract class HttpHeaders : IHeaderDictionary, IDictionary<string, StringValues>, ICollection<KeyValuePair<string, StringValues>>, IEnumerable<KeyValuePair<string, StringValues>>, IEnumerable
{
	protected long _bits;

	protected long? _contentLength;

	protected bool _isReadOnly;

	protected Dictionary<string, StringValues>? MaybeUnknown;

	private static readonly string KeepAlive = "keep-alive";

	private static readonly StringValues ConnectionValueKeepAlive = KeepAlive;

	private static readonly StringValues ConnectionValueClose = "close";

	private static readonly StringValues ConnectionValueUpgrade = HeaderNames.Upgrade;

	private static readonly HashSet<string> _internedHeaderNames = new HashSet<string>(91, StringComparer.OrdinalIgnoreCase)
	{
		HeaderNames.Accept,
		HeaderNames.AcceptCharset,
		HeaderNames.AcceptEncoding,
		HeaderNames.AcceptLanguage,
		HeaderNames.AcceptRanges,
		HeaderNames.AccessControlAllowCredentials,
		HeaderNames.AccessControlAllowHeaders,
		HeaderNames.AccessControlAllowMethods,
		HeaderNames.AccessControlAllowOrigin,
		HeaderNames.AccessControlExposeHeaders,
		HeaderNames.AccessControlMaxAge,
		HeaderNames.AccessControlRequestHeaders,
		HeaderNames.AccessControlRequestMethod,
		HeaderNames.Age,
		HeaderNames.Allow,
		HeaderNames.AltSvc,
		HeaderNames.Authorization,
		HeaderNames.Baggage,
		HeaderNames.CacheControl,
		HeaderNames.Connection,
		HeaderNames.ContentDisposition,
		HeaderNames.ContentEncoding,
		HeaderNames.ContentLanguage,
		HeaderNames.ContentLength,
		HeaderNames.ContentLocation,
		HeaderNames.ContentMD5,
		HeaderNames.ContentRange,
		HeaderNames.ContentSecurityPolicy,
		HeaderNames.ContentSecurityPolicyReportOnly,
		HeaderNames.ContentType,
		HeaderNames.CorrelationContext,
		HeaderNames.Cookie,
		HeaderNames.Date,
		HeaderNames.DNT,
		HeaderNames.ETag,
		HeaderNames.Expires,
		HeaderNames.Expect,
		HeaderNames.From,
		HeaderNames.GrpcAcceptEncoding,
		HeaderNames.GrpcEncoding,
		HeaderNames.GrpcMessage,
		HeaderNames.GrpcStatus,
		HeaderNames.GrpcTimeout,
		HeaderNames.Host,
		HeaderNames.KeepAlive,
		HeaderNames.IfMatch,
		HeaderNames.IfModifiedSince,
		HeaderNames.IfNoneMatch,
		HeaderNames.IfRange,
		HeaderNames.IfUnmodifiedSince,
		HeaderNames.LastModified,
		HeaderNames.Link,
		HeaderNames.Location,
		HeaderNames.MaxForwards,
		HeaderNames.Origin,
		HeaderNames.Pragma,
		HeaderNames.ProxyAuthenticate,
		HeaderNames.ProxyAuthorization,
		HeaderNames.ProxyConnection,
		HeaderNames.Range,
		HeaderNames.Referer,
		HeaderNames.RetryAfter,
		HeaderNames.RequestId,
		HeaderNames.SecWebSocketAccept,
		HeaderNames.SecWebSocketKey,
		HeaderNames.SecWebSocketProtocol,
		HeaderNames.SecWebSocketVersion,
		HeaderNames.SecWebSocketExtensions,
		HeaderNames.Server,
		HeaderNames.SetCookie,
		HeaderNames.StrictTransportSecurity,
		HeaderNames.TE,
		HeaderNames.Trailer,
		HeaderNames.TransferEncoding,
		HeaderNames.Translate,
		HeaderNames.TraceParent,
		HeaderNames.TraceState,
		HeaderNames.Upgrade,
		HeaderNames.UpgradeInsecureRequests,
		HeaderNames.UserAgent,
		HeaderNames.Vary,
		HeaderNames.Via,
		HeaderNames.Warning,
		HeaderNames.WebSocketSubProtocols,
		HeaderNames.WWWAuthenticate,
		HeaderNames.XContentTypeOptions,
		HeaderNames.XFrameOptions,
		HeaderNames.XPoweredBy,
		HeaderNames.XRequestedWith,
		HeaderNames.XUACompatible,
		HeaderNames.XXSSProtection
	};

	protected Dictionary<string, StringValues> Unknown => MaybeUnknown ?? (MaybeUnknown = new Dictionary<string, StringValues>(StringComparer.OrdinalIgnoreCase));

	public long? ContentLength
	{
		get
		{
			return _contentLength;
		}
		set
		{
			if (_isReadOnly)
			{
				ThrowHeadersReadOnlyException();
			}
			if (value.HasValue && value.Value < 0)
			{
				ThrowInvalidContentLengthException(value.Value);
			}
			_contentLength = value;
		}
	}

	public abstract StringValues HeaderConnection { get; set; }

	StringValues IHeaderDictionary.this[string key]
	{
		get
		{
			if (TryGetValueFast(key, out var value))
			{
				return value;
			}
			return StringValues.Empty;
		}
		set
		{
			if (_isReadOnly)
			{
				ThrowHeadersReadOnlyException();
			}
			if (string.IsNullOrEmpty(key))
			{
				ThrowInvalidEmptyHeaderName();
			}
			if (value.Count == 0)
			{
				RemoveFast(key);
			}
			else
			{
				SetValueFast(key, value);
			}
		}
	}

	StringValues IDictionary<string, StringValues>.this[string key]
	{
		get
		{
			if (!TryGetValueFast(key, out var value))
			{
				ThrowKeyNotFoundException();
			}
			return value;
		}
		set
		{
			((IHeaderDictionary)this)[key] = value;
		}
	}

	public int Count => GetCountFast();

	bool ICollection<KeyValuePair<string, StringValues>>.IsReadOnly => _isReadOnly;

	ICollection<string> IDictionary<string, StringValues>.Keys => this.Select((KeyValuePair<string, StringValues> pair) => pair.Key).ToHashSet(StringComparer.OrdinalIgnoreCase);

	ICollection<StringValues> IDictionary<string, StringValues>.Values => this.Select((KeyValuePair<string, StringValues> pair) => pair.Value).ToList();

	protected static void ThrowHeadersReadOnlyException()
	{
		throw new InvalidOperationException(CoreStrings.HeadersAreReadOnly);
	}

	protected static void ThrowArgumentException()
	{
		throw new ArgumentException();
	}

	private static void ThrowKeyNotFoundException()
	{
		throw new KeyNotFoundException();
	}

	protected static void ThrowDuplicateKeyException()
	{
		throw new ArgumentException(CoreStrings.KeyAlreadyExists);
	}

	public void SetReadOnly()
	{
		_isReadOnly = true;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	public void Reset()
	{
		_isReadOnly = false;
		ClearFast();
	}

	protected static string GetInternedHeaderName(string name)
	{
		if (_internedHeaderNames.TryGetValue(name, out var actualValue))
		{
			return actualValue;
		}
		return name;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	protected static StringValues AppendValue(StringValues existing, string append)
	{
		return StringValues.Concat(in existing, append);
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	protected bool TryGetUnknown(string key, ref StringValues value)
	{
		return MaybeUnknown?.TryGetValue(key, out value) ?? false;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	protected bool RemoveUnknown(string key)
	{
		return MaybeUnknown?.Remove(key) ?? false;
	}

	protected virtual int GetCountFast()
	{
		throw new NotImplementedException();
	}

	protected virtual bool TryGetValueFast(string key, out StringValues value)
	{
		throw new NotImplementedException();
	}

	protected virtual void SetValueFast(string key, StringValues value)
	{
		throw new NotImplementedException();
	}

	protected virtual bool AddValueFast(string key, StringValues value)
	{
		throw new NotImplementedException();
	}

	protected virtual bool RemoveFast(string key)
	{
		throw new NotImplementedException();
	}

	protected virtual void ClearFast()
	{
		throw new NotImplementedException();
	}

	protected virtual bool CopyToFast(KeyValuePair<string, StringValues>[] array, int arrayIndex)
	{
		throw new NotImplementedException();
	}

	protected virtual IEnumerator<KeyValuePair<string, StringValues>> GetEnumeratorFast()
	{
		throw new NotImplementedException();
	}

	void ICollection<KeyValuePair<string, StringValues>>.Add(KeyValuePair<string, StringValues> item)
	{
		((IDictionary<string, StringValues>)this).Add(item.Key, item.Value);
	}

	void IDictionary<string, StringValues>.Add(string key, StringValues value)
	{
		if (_isReadOnly)
		{
			ThrowHeadersReadOnlyException();
		}
		if (string.IsNullOrEmpty(key))
		{
			ThrowInvalidEmptyHeaderName();
		}
		if (value.Count > 0 && !AddValueFast(key, value))
		{
			ThrowDuplicateKeyException();
		}
	}

	void ICollection<KeyValuePair<string, StringValues>>.Clear()
	{
		if (_isReadOnly)
		{
			ThrowHeadersReadOnlyException();
		}
		ClearFast();
	}

	bool ICollection<KeyValuePair<string, StringValues>>.Contains(KeyValuePair<string, StringValues> item)
	{
		if (TryGetValueFast(item.Key, out var value))
		{
			return value.Equals(item.Value);
		}
		return false;
	}

	bool IDictionary<string, StringValues>.ContainsKey(string key)
	{
		StringValues value;
		return TryGetValueFast(key, out value);
	}

	void ICollection<KeyValuePair<string, StringValues>>.CopyTo(KeyValuePair<string, StringValues>[] array, int arrayIndex)
	{
		if (!CopyToFast(array, arrayIndex))
		{
			ThrowArgumentException();
		}
	}

	IEnumerator IEnumerable.GetEnumerator()
	{
		return GetEnumeratorFast();
	}

	IEnumerator<KeyValuePair<string, StringValues>> IEnumerable<KeyValuePair<string, StringValues>>.GetEnumerator()
	{
		return GetEnumeratorFast();
	}

	bool ICollection<KeyValuePair<string, StringValues>>.Remove(KeyValuePair<string, StringValues> item)
	{
		if (TryGetValueFast(item.Key, out var value) && value.Equals(item.Value))
		{
			return RemoveFast(item.Key);
		}
		return false;
	}

	bool IDictionary<string, StringValues>.Remove(string key)
	{
		if (_isReadOnly)
		{
			ThrowHeadersReadOnlyException();
		}
		return RemoveFast(key);
	}

	bool IDictionary<string, StringValues>.TryGetValue(string key, out StringValues value)
	{
		return TryGetValueFast(key, out value);
	}

	internal string DebuggerToString()
	{
		string text = $"Count = {Count}";
		if (_isReadOnly)
		{
			text += ", IsReadOnly = true";
		}
		return text;
	}

	public static void ValidateHeaderValueCharacters(string headerName, StringValues headerValues, Func<string, Encoding?> encodingSelector)
	{
		bool requireAscii = (object)encodingSelector == KestrelServerOptions.DefaultHeaderEncodingSelector || encodingSelector(headerName) == null;
		int count = headerValues.Count;
		for (int i = 0; i < count; i++)
		{
			ValidateHeaderValueCharacters(headerValues[i] ?? string.Empty, requireAscii);
		}
	}

	public static void ValidateHeaderValueCharacters(string headerCharacters, bool requireAscii)
	{
		if (headerCharacters != null)
		{
			int num = (requireAscii ? HttpCharacters.IndexOfInvalidFieldValueChar(headerCharacters) : HttpCharacters.IndexOfInvalidFieldValueCharExtended(headerCharacters));
			if (num >= 0)
			{
				ThrowInvalidHeaderCharacter(headerCharacters[num]);
			}
		}
	}

	public static void ValidateHeaderNameCharacters(string headerCharacters)
	{
		int num = HttpCharacters.IndexOfInvalidTokenChar(headerCharacters);
		if (num >= 0)
		{
			ThrowInvalidHeaderCharacter(headerCharacters[num]);
		}
	}

	public static ConnectionOptions ParseConnection(HttpHeaders headers)
	{
		StringValues headerConnection = headers.HeaderConnection;
		int count = headerConnection.Count;
		if (count == 0)
		{
			return ConnectionOptions.None;
		}
		ConnectionOptions connectionOptions = ConnectionOptions.None;
		if (count == 1 && (object)headerConnection.ToString() == KeepAlive)
		{
			return ConnectionOptions.KeepAlive;
		}
		for (int i = 0; i < count; i++)
		{
			ReadOnlySpan<char> span = headerConnection[i];
			while (span.Length > 0)
			{
				char c = '\0';
				int j;
				for (j = 0; j < span.Length; j++)
				{
					c = span[j];
					if (c != ' ' && c != ',')
					{
						break;
					}
				}
				j++;
				if ((uint)j > (uint)span.Length)
				{
					break;
				}
				span = span.Slice(j);
				c = ToLowerCase(c);
				ReadOnlySpan<byte> value = MemoryMarshal.AsBytes(span);
				j = 0;
				ConnectionOptions connectionOptions2 = ConnectionOptions.None;
				if (c == 'k' && value.Length >= 18)
				{
					if (ReadLowerCaseUInt64(value, 137441050656uL) == 12666854994935909L)
					{
						j += 4;
						value = value.Slice(8);
						if (ReadLowerCaseUInt64(value) == 33214498230501473L)
						{
							j += 4;
							value = value.Slice(8);
							if (ReadLowerCaseUInt16(value) == 101)
							{
								j++;
								connectionOptions2 = ConnectionOptions.KeepAlive;
							}
						}
					}
				}
				else if (c == 'u' && value.Length >= 12)
				{
					if (ReadLowerCaseUInt64(value) == 27303562373955696L)
					{
						j += 4;
						value = value.Slice(8);
						if (ReadLowerCaseUInt32(value) == 6619236)
						{
							j += 2;
							connectionOptions2 = ConnectionOptions.Upgrade;
						}
					}
				}
				else if (c == 'c' && value.Length >= 8 && ReadLowerCaseUInt64(value) == 28429466576289900L)
				{
					j += 4;
					connectionOptions2 = ConnectionOptions.Close;
				}
				if ((uint)j >= (uint)span.Length)
				{
					connectionOptions |= connectionOptions2;
					break;
				}
				span = span.Slice(j);
				for (j = 0; j < span.Length; j++)
				{
					c = span[j];
					switch (c)
					{
					default:
						connectionOptions2 = ConnectionOptions.None;
						continue;
					case ' ':
						continue;
					case ',':
						break;
					}
					break;
				}
				if ((uint)j >= (uint)span.Length)
				{
					connectionOptions |= connectionOptions2;
					break;
				}
				if (c == ',')
				{
					connectionOptions |= connectionOptions2;
					j++;
					if ((uint)j >= (uint)span.Length)
					{
						break;
					}
					span = span.Slice(j);
				}
			}
		}
		switch (connectionOptions)
		{
		case ConnectionOptions.Upgrade:
			headers.HeaderConnection = ConnectionValueUpgrade;
			break;
		case ConnectionOptions.KeepAlive:
			headers.HeaderConnection = ConnectionValueKeepAlive;
			break;
		case ConnectionOptions.Close:
			headers.HeaderConnection = ConnectionValueClose;
			break;
		}
		return connectionOptions;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static ulong ReadLowerCaseUInt64(ReadOnlySpan<byte> value, ulong lowerCaseMask = 9007336695791648uL)
	{
		ulong num = MemoryMarshal.Read<ulong>(value);
		if (!BitConverter.IsLittleEndian)
		{
			num = ((num & 0xFFFF000000000000uL) >> 48) | ((num & 0xFFFF00000000L) >> 16) | ((num & 0xFFFF0000u) << 16) | ((num & 0xFFFF) << 48);
		}
		return num | lowerCaseMask;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static uint ReadLowerCaseUInt32(ReadOnlySpan<byte> value)
	{
		uint num = MemoryMarshal.Read<uint>(value);
		if (!BitConverter.IsLittleEndian)
		{
			num = ((num & 0xFFFF0000u) >> 16) | ((num & 0xFFFF) << 16);
		}
		return num | 0x200020;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static ushort ReadLowerCaseUInt16(ReadOnlySpan<byte> value)
	{
		return (ushort)(MemoryMarshal.Read<ushort>(value) | 0x20);
	}

	private static char ToLowerCase(char value)
	{
		return (char)(value | 0x20);
	}

	public static TransferCoding GetFinalTransferCoding(StringValues transferEncoding)
	{
		TransferCoding result = TransferCoding.None;
		int count = transferEncoding.Count;
		for (int i = 0; i < count; i++)
		{
			ReadOnlySpan<char> span = transferEncoding[i];
			while (span.Length > 0)
			{
				char c = '\0';
				int j;
				for (j = 0; j < span.Length; j++)
				{
					c = span[j];
					if (c != ' ' && c != ',')
					{
						break;
					}
				}
				j++;
				if ((uint)j > (uint)span.Length)
				{
					break;
				}
				span = span.Slice(j);
				j = 0;
				ReadOnlySpan<byte> byteValue = MemoryMarshal.AsBytes(span);
				if (ToLowerCase(c) == 'c' && TryReadLowerCaseUInt64(byteValue, out var value) && value == 30118294962110568L)
				{
					j += 4;
					byteValue = byteValue.Slice(8);
					if (TryReadLowerCaseUInt32(byteValue, out var value2) && value2 == 6553701)
					{
						j += 2;
						result = TransferCoding.Chunked;
					}
					else
					{
						result = TransferCoding.Other;
					}
				}
				else
				{
					result = TransferCoding.Other;
				}
				if ((uint)j >= (uint)span.Length)
				{
					break;
				}
				span = span.Slice(j);
				for (j = 0; j < span.Length; j++)
				{
					c = span[j];
					switch (c)
					{
					default:
						result = TransferCoding.Other;
						continue;
					case ' ':
						continue;
					case ',':
						break;
					}
					break;
				}
				if ((uint)j >= (uint)span.Length)
				{
					break;
				}
				if (c == ',')
				{
					j++;
					if ((uint)j >= (uint)span.Length)
					{
						break;
					}
					span = span.Slice(j);
				}
			}
		}
		return result;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static bool TryReadLowerCaseUInt64(ReadOnlySpan<byte> byteValue, out ulong value)
	{
		if (MemoryMarshal.TryRead<ulong>(byteValue, out var value2))
		{
			if (!BitConverter.IsLittleEndian)
			{
				value2 = ((value2 & 0xFFFF000000000000uL) >> 48) | ((value2 & 0xFFFF00000000L) >> 16) | ((value2 & 0xFFFF0000u) << 16) | ((value2 & 0xFFFF) << 48);
			}
			value = value2 | 0x20002000200020L;
			return true;
		}
		value = 0uL;
		return false;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static bool TryReadLowerCaseUInt32(ReadOnlySpan<byte> byteValue, out uint value)
	{
		if (MemoryMarshal.TryRead<uint>(byteValue, out var value2))
		{
			if (!BitConverter.IsLittleEndian)
			{
				value2 = ((value2 & 0xFFFF0000u) >> 16) | ((value2 & 0xFFFF) << 16);
			}
			value = value2 | 0x200020;
			return true;
		}
		value = 0u;
		return false;
	}

	private static void ThrowInvalidContentLengthException(long value)
	{
		throw new ArgumentOutOfRangeException(CoreStrings.FormatInvalidContentLength_InvalidNumber(value));
	}

	private static void ThrowInvalidHeaderCharacter(char ch)
	{
		throw new InvalidOperationException(CoreStrings.FormatInvalidAsciiOrControlChar(string.Format(CultureInfo.InvariantCulture, "0x{0:X4}", (ushort)ch)));
	}

	private static void ThrowInvalidEmptyHeaderName()
	{
		throw new InvalidOperationException(CoreStrings.InvalidEmptyHeaderName);
	}
}
