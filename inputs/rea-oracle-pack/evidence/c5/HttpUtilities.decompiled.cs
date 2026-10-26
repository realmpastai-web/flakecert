using System;
using System.Buffers;
using System.Buffers.Binary;
using System.Globalization;
using System.Net;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;

internal static class HttpUtilities
{
	public const string HttpUriScheme = "http://";

	public const string HttpsUriScheme = "https://";

	private static readonly ulong _httpSchemeLong;

	private static readonly ulong _httpsSchemeLong;

	private const uint _httpGetMethodInt = 542393671u;

	private const ulong _http10VersionLong = 3471766442030158920uL;

	private const ulong _http11VersionLong = 3543824036068086856uL;

	private static readonly UTF8Encoding DefaultRequestHeaderEncoding;

	private static readonly string[] WordListForPerfectHashOfMethods;

	private static readonly ulong _httpConnectMethodLong;

	private static readonly ulong _httpDeleteMethodLong;

	private static readonly ulong _httpHeadMethodLong;

	private static readonly ulong _httpPatchMethodLong;

	private static readonly ulong _httpPostMethodLong;

	private static readonly ulong _httpPutMethodLong;

	private static readonly ulong _httpOptionsMethodLong;

	private static readonly ulong _httpTraceMethodLong;

	private static readonly ulong _mask8Chars;

	private static readonly ulong _mask7Chars;

	private static readonly ulong _mask6Chars;

	private static readonly ulong _mask5Chars;

	private static readonly ulong _mask4Chars;

	private static readonly Tuple<ulong, ulong, HttpMethod, int>[] _knownMethods;

	private static readonly string[] _methodNames;

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static void SetKnownMethod(ulong mask, ulong knownMethodUlong, HttpMethod knownMethod, int length)
	{
		_knownMethods[GetKnownMethodIndex(knownMethodUlong)] = new Tuple<ulong, ulong, HttpMethod, int>(mask, knownMethodUlong, knownMethod, length);
	}

	private static void FillKnownMethodsGaps()
	{
		Tuple<ulong, ulong, HttpMethod, int>[] knownMethods = _knownMethods;
		int num = knownMethods.Length;
		Tuple<ulong, ulong, HttpMethod, int> tuple = new Tuple<ulong, ulong, HttpMethod, int>(_mask8Chars, 0uL, HttpMethod.Custom, 0);
		for (int i = 0; i < num; i++)
		{
			if (knownMethods[i] == null)
			{
				knownMethods[i] = tuple;
			}
		}
	}

	private static ulong GetAsciiStringAsLong(string str)
	{
		Span<byte> span = stackalloc byte[8];
		Ascii.FromUtf16(str, span, out var _);
		return BinaryPrimitives.ReadUInt64LittleEndian(span);
	}

	private static uint GetAsciiStringAsInt(string str)
	{
		Span<byte> span = stackalloc byte[4];
		Ascii.FromUtf16(str, span, out var _);
		return BinaryPrimitives.ReadUInt32LittleEndian(span);
	}

	private static ulong GetMaskAsLong(ReadOnlySpan<byte> bytes)
	{
		return BinaryPrimitives.ReadUInt64LittleEndian(bytes);
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	public static string GetHeaderName(this ReadOnlySpan<byte> span)
	{
		if (span.IsEmpty)
		{
			return string.Empty;
		}
		return string.Create<ReadOnlySpan<byte>>(span.Length, span, (SpanAction<char, ReadOnlySpan<byte>>)((Span<char> destination, ReadOnlySpan<byte> source) =>
		{
			if (source.Contains((byte)0) || Ascii.ToUtf16(source, destination, out var _) != OperationStatus.Done)
			{
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidCharactersInHeaderName);
			}
		}));
	}

	public static string GetAsciiString(this Span<byte> span)
	{
		return StringUtilities.GetAsciiString(span);
	}

	public static string GetAsciiOrUTF8String(this ReadOnlySpan<byte> span)
	{
		return span.GetAsciiOrUTF8String(DefaultRequestHeaderEncoding);
	}

	public static string GetRequestHeaderString(this ReadOnlySpan<byte> span, string name, Func<string, Encoding?> encodingSelector, bool checkForNewlineChars)
	{
		string text = (((object)KestrelServerOptions.DefaultHeaderEncodingSelector != encodingSelector) ? span.GetRequestHeaderStringWithoutDefaultEncodingCore(name, encodingSelector) : span.GetAsciiOrUTF8String(DefaultRequestHeaderEncoding));
		if (checkForNewlineChars ? text.ContainsAny('\r', '\n', '\0') : MemoryExtensions.Contains(text, '\0'))
		{
			ThrowForInvalidCharacter(checkForNewlineChars);
		}
		return text;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private static void ThrowForInvalidCharacter(bool checkForNewlines)
	{
		if (checkForNewlines)
		{
			throw new InvalidOperationException("Newline characters (CR/LF) or Null are not allowed in request headers.");
		}
		throw new InvalidOperationException("Null characters are not allowed in request headers.");
	}

	private static string GetRequestHeaderStringWithoutDefaultEncodingCore(this ReadOnlySpan<byte> span, string name, Func<string, Encoding> encodingSelector)
	{
		Encoding encoding = encodingSelector(name);
		if (encoding == null)
		{
			return span.GetAsciiOrUTF8String(DefaultRequestHeaderEncoding);
		}
		if (encoding == Encoding.Latin1)
		{
			return span.GetLatin1String();
		}
		try
		{
			return encoding.GetString(span);
		}
		catch (DecoderFallbackException ex)
		{
			throw new InvalidOperationException(ex.Message, ex);
		}
	}

	public static string GetAsciiStringEscaped(this ReadOnlySpan<byte> span, int maxChars)
	{
		StringBuilder stringBuilder = new StringBuilder();
		for (int i = 0; i < Math.Min(span.Length, maxChars); i++)
		{
			byte b = span[i];
			string value;
			if (b >= 32 && b < 127)
			{
				char c = (char)b;
				value = c.ToString();
			}
			else
			{
				value = $"\\x{b:X2}";
			}
			stringBuilder.Append(value);
		}
		if (span.Length > maxChars)
		{
			stringBuilder.Append("...");
		}
		return stringBuilder.ToString();
	}

	public static bool GetKnownMethod(this ReadOnlySpan<byte> span, out HttpMethod method, out int length)
	{
		method = span.GetKnownMethod(out length);
		return method != HttpMethod.Custom;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	public static HttpMethod GetKnownMethod(this ReadOnlySpan<byte> span, out int methodLength)
	{
		methodLength = 0;
		if (4 <= span.Length)
		{
			if (BinaryPrimitives.ReadUInt32LittleEndian(span) == 542393671)
			{
				methodLength = 3;
				return HttpMethod.Get;
			}
			if (8 <= span.Length)
			{
				ulong num = BinaryPrimitives.ReadUInt64LittleEndian(span);
				int knownMethodIndex = GetKnownMethodIndex(num);
				Tuple<ulong, ulong, HttpMethod, int>[] knownMethods = _knownMethods;
				if ((uint)knownMethodIndex < (uint)knownMethods.Length)
				{
					Tuple<ulong, ulong, HttpMethod, int> tuple = _knownMethods[knownMethodIndex];
					if (tuple != null && (num & tuple.Item1) == tuple.Item2)
					{
						methodLength = tuple.Item4;
						return tuple.Item3;
					}
				}
			}
		}
		return HttpMethod.Custom;
	}

	public static HttpMethod GetKnownMethod(string? value)
	{
		if (string.IsNullOrEmpty(value))
		{
			return HttpMethod.None;
		}
		if ((uint)(value.Length - 3) <= 4u)
		{
			ReadOnlySpan<HttpMethod> readOnlySpan = Methods();
			uint num = PerfectHash(value);
			if (num < (uint)WordListForPerfectHashOfMethods.Length && WordListForPerfectHashOfMethods[num] == value && num < (uint)readOnlySpan.Length)
			{
				return readOnlySpan[(int)num];
			}
		}
		return HttpMethod.Custom;
		static ReadOnlySpan<HttpMethod> Methods()
		{
			return new HttpMethod[13]
			{
				HttpMethod.None,
				HttpMethod.None,
				HttpMethod.None,
				HttpMethod.Get,
				HttpMethod.Head,
				HttpMethod.Trace,
				HttpMethod.Delete,
				HttpMethod.Options,
				HttpMethod.Put,
				HttpMethod.Post,
				HttpMethod.Patch,
				HttpMethod.None,
				HttpMethod.Connect
			};
		}
		[MethodImpl(MethodImplOptions.AggressiveInlining)]
		static uint PerfectHash(ReadOnlySpan<char> str)
		{
			ReadOnlySpan<byte> readOnlySpan2 = new byte[256]
			{
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 5, 0, 13,
				13, 0, 0, 13, 13, 13, 13, 13, 13, 0,
				5, 13, 13, 13, 0, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
				13, 13, 13, 13, 13, 13
			};
			char reference = MemoryMarshal.GetReference(str);
			return (uint)(str.Length + readOnlySpan2[reference]);
		}
	}

	public static bool GetKnownVersion(this ReadOnlySpan<byte> span, out Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion knownVersion, out byte length)
	{
		if (span.Length > 8 && span[8] == 13)
		{
			knownVersion = span.GetKnownVersion();
			if (knownVersion != Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Unknown)
			{
				length = 8;
				return true;
			}
		}
		knownVersion = Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Unknown;
		length = 0;
		return false;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	internal static Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion GetKnownVersion(this ReadOnlySpan<byte> span)
	{
		if (BinaryPrimitives.TryReadUInt64LittleEndian(span, out var value))
		{
			switch (value)
			{
			case 3543824036068086856uL:
				return Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http11;
			case 3471766442030158920uL:
				return Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http10;
			}
		}
		return Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Unknown;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	public static bool GetKnownHttpScheme(this Span<byte> span, out HttpScheme knownScheme)
	{
		if (BinaryPrimitives.TryReadUInt64LittleEndian(span, out var value))
		{
			if ((value & _mask7Chars) == _httpSchemeLong)
			{
				knownScheme = HttpScheme.Http;
				return true;
			}
			if (value == _httpsSchemeLong)
			{
				knownScheme = HttpScheme.Https;
				return true;
			}
		}
		knownScheme = HttpScheme.Unknown;
		return false;
	}

	public static string VersionToString(Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion httpVersion)
	{
		return httpVersion switch
		{
			Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http10 => Microsoft.AspNetCore.Http.HttpProtocol.Http10, 
			Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http11 => Microsoft.AspNetCore.Http.HttpProtocol.Http11, 
			Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http2 => Microsoft.AspNetCore.Http.HttpProtocol.Http2, 
			Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpVersion.Http3 => Microsoft.AspNetCore.Http.HttpProtocol.Http3, 
			_ => null, 
		};
	}

	public static string? MethodToString(HttpMethod method)
	{
		string[] methodNames = _methodNames;
		if ((uint)method < (uint)methodNames.Length)
		{
			return methodNames[(uint)method];
		}
		return null;
	}

	public static string? SchemeToString(HttpScheme scheme)
	{
		return scheme switch
		{
			HttpScheme.Http => "http://", 
			HttpScheme.Https => "https://", 
			_ => null, 
		};
	}

	public static bool IsHostHeaderValid(string hostText)
	{
		if (string.IsNullOrEmpty(hostText))
		{
			return true;
		}
		switch (hostText[0])
		{
		case '[':
			return IsIPv6HostValid(hostText);
		case ':':
			return false;
		default:
		{
			int num = HttpCharacters.IndexOfInvalidHostChar(hostText);
			if (num >= 0)
			{
				return IsHostPortValid(hostText, num);
			}
			return true;
		}
		}
	}

	private static bool IsIPv6HostValid(string hostText)
	{
		for (int i = 1; i < hostText.Length; i++)
		{
			char c = hostText[i];
			if (c == ']')
			{
				if (i < 4)
				{
					return false;
				}
				if (i + 1 < hostText.Length)
				{
					return IsHostPortValid(hostText, i + 1);
				}
				return true;
			}
			if (!IsHex(c) && c != ':' && c != '.')
			{
				return false;
			}
		}
		return false;
	}

	private static bool IsHostPortValid(string hostText, int offset)
	{
		char c = hostText[offset];
		offset++;
		if (c != ':' || offset == hostText.Length)
		{
			return false;
		}
		for (int i = offset; i < hostText.Length; i++)
		{
			if (!IsNumeric(hostText[i]))
			{
				return false;
			}
		}
		return true;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static bool IsNumeric(char ch)
	{
		return (uint)(ch - 48) < 10u;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static bool IsHex(char ch)
	{
		if (!IsNumeric(ch))
		{
			return (uint)((ch | 0x20) - 97) < 6u;
		}
		return true;
	}

	public static AltSvcHeader? GetEndpointAltSvc(IPEndPoint endpoint, HttpProtocols protocols)
	{
		bool num = protocols.HasFlag(HttpProtocols.Http1) || protocols.HasFlag(HttpProtocols.Http2);
		bool flag = protocols.HasFlag(HttpProtocols.Http3);
		if (num & flag)
		{
			string text = "h3=\":" + endpoint.Port.ToString(CultureInfo.InvariantCulture) + "\"; ma=86400";
			byte[] bytes = Encoding.ASCII.GetBytes("\r\nAlt-Svc: " + text);
			return new AltSvcHeader(text, bytes);
		}
		return null;
	}

	static HttpUtilities()
	{
		_httpSchemeLong = GetAsciiStringAsLong("http://\0");
		_httpsSchemeLong = GetAsciiStringAsLong("https://");
		DefaultRequestHeaderEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true);
		WordListForPerfectHashOfMethods = new string[13]
		{
			"", "", "", "GET", "HEAD", "TRACE", "DELETE", "OPTIONS", "PUT", "POST",
			"PATCH", "", "CONNECT"
		};
		_httpConnectMethodLong = GetAsciiStringAsLong("CONNECT ");
		_httpDeleteMethodLong = GetAsciiStringAsLong("DELETE \0");
		_httpHeadMethodLong = GetAsciiStringAsLong("HEAD \0\0\0");
		_httpPatchMethodLong = GetAsciiStringAsLong("PATCH \0\0");
		_httpPostMethodLong = GetAsciiStringAsLong("POST \0\0\0");
		_httpPutMethodLong = GetAsciiStringAsLong("PUT \0\0\0\0");
		_httpOptionsMethodLong = GetAsciiStringAsLong("OPTIONS ");
		_httpTraceMethodLong = GetAsciiStringAsLong("TRACE \0\0");
		_mask8Chars = GetMaskAsLong(new byte[8] { 255, 255, 255, 255, 255, 255, 255, 255 });
		_mask7Chars = GetMaskAsLong(new byte[8] { 255, 255, 255, 255, 255, 255, 255, 0 });
		_mask6Chars = GetMaskAsLong(new byte[8] { 255, 255, 255, 255, 255, 255, 0, 0 });
		_mask5Chars = GetMaskAsLong(new byte[8] { 255, 255, 255, 255, 255, 0, 0, 0 });
		_mask4Chars = GetMaskAsLong(new byte[8] { 255, 255, 255, 255, 0, 0, 0, 0 });
		_knownMethods = new Tuple<ulong, ulong, HttpMethod, int>[17];
		_methodNames = new string[9];
		SetKnownMethod(_mask4Chars, _httpPutMethodLong, HttpMethod.Put, 3);
		SetKnownMethod(_mask5Chars, _httpHeadMethodLong, HttpMethod.Head, 4);
		SetKnownMethod(_mask5Chars, _httpPostMethodLong, HttpMethod.Post, 4);
		SetKnownMethod(_mask6Chars, _httpPatchMethodLong, HttpMethod.Patch, 5);
		SetKnownMethod(_mask6Chars, _httpTraceMethodLong, HttpMethod.Trace, 5);
		SetKnownMethod(_mask7Chars, _httpDeleteMethodLong, HttpMethod.Delete, 6);
		SetKnownMethod(_mask8Chars, _httpConnectMethodLong, HttpMethod.Connect, 7);
		SetKnownMethod(_mask8Chars, _httpOptionsMethodLong, HttpMethod.Options, 7);
		FillKnownMethodsGaps();
		_methodNames[7] = HttpMethods.Connect;
		_methodNames[2] = HttpMethods.Delete;
		_methodNames[0] = HttpMethods.Get;
		_methodNames[4] = HttpMethods.Head;
		_methodNames[8] = HttpMethods.Options;
		_methodNames[6] = HttpMethods.Patch;
		_methodNames[3] = HttpMethods.Post;
		_methodNames[1] = HttpMethods.Put;
		_methodNames[5] = HttpMethods.Trace;
	}

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	private static int GetKnownMethodIndex(ulong value)
	{
		int num = (int)value & 0x600000C;
		return ((num >> 2) | (num >> 23)) & 0xF;
	}
}
