using System;
using System.Buffers;
using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;

public class HttpParser<TRequestHandler> : IHttpParser<TRequestHandler> where TRequestHandler : IHttpHeadersHandler, IHttpRequestLineHandler
{
	private readonly bool _showErrorDetails;

	private readonly bool _disableHttp1LineFeedTerminators;

	private const byte ByteCR = 13;

	private const byte ByteLF = 10;

	private const byte ByteColon = 58;

	private const byte ByteSpace = 32;

	private const byte ByteTab = 9;

	private const byte ByteQuestionMark = 63;

	private const byte BytePercentage = 37;

	private const int MinTlsRequestSize = 1;

	private static ReadOnlySpan<byte> RequestLineDelimiters => "\n\0"u8;

	public HttpParser()
		: this(true)
	{
	}

	public HttpParser(bool showErrorDetails)
		: this(showErrorDetails, AppContext.TryGetSwitch("Microsoft.AspNetCore.Server.Kestrel.DisableHttp1LineFeedTerminators", out var isEnabled) & isEnabled)
	{
	}

	internal HttpParser(bool showErrorDetails, bool disableHttp1LineFeedTerminators)
	{
		_showErrorDetails = showErrorDetails;
		_disableHttp1LineFeedTerminators = disableHttp1LineFeedTerminators;
	}

	public bool ParseRequestLine(TRequestHandler handler, ref SequenceReader<byte> reader)
	{
		if (!reader.TryReadToAny(out ReadOnlySpan<byte> span, RequestLineDelimiters, false))
		{
			return false;
		}
		reader.TryRead(out var value);
		if (value == 0 || span.Length == 0)
		{
			reader.Rewind(span.Length + 1);
			reader.TryReadExact(span.Length + 1, out var sequence);
			span = (sequence.IsSingleSegment ? sequence.FirstSpan : ((ReadOnlySpan<byte>)BuffersExtensions.ToArray(in sequence)));
			RejectRequestLine(span);
		}
		HttpMethod knownMethod = span.GetKnownMethod(out var methodLength);
		if (knownMethod == HttpMethod.Custom)
		{
			methodLength = GetUnknownMethodLength(span);
		}
		HttpVersionAndMethod versionAndMethod = new HttpVersionAndMethod(knownMethod, methodLength);
		int num = methodLength + 1;
		if ((uint)num >= (uint)span.Length)
		{
			RejectRequestLine(span);
		}
		byte b = span[num];
		if (b == 32 || b == 63 || b == 37)
		{
			RejectRequestLine(span);
		}
		int num2 = num;
		bool isEncoded = false;
		num++;
		int num3 = span.Slice(num).IndexOfAny((byte)32, (byte)63, (byte)37);
		if (num3 >= 0)
		{
			if (span[num + num3] == 37)
			{
				isEncoded = true;
				num += num3;
				num3 = span.Slice(num).IndexOfAny((byte)32, (byte)63);
			}
			num += num3;
			b = span[num];
		}
		TargetOffsetPathLength targetPath = new TargetOffsetPathLength(num2, num - num2, isEncoded);
		if (b == 63)
		{
			for (; (uint)num < (uint)span.Length; num++)
			{
				b = span[num];
				if (b == 32)
				{
					break;
				}
			}
		}
		int length = num;
		for (num++; (uint)num < (uint)span.Length && span[num] == 32; num++)
		{
		}
		if ((num + 9 != span.Length || span[num + 8] != 13) && (_disableHttp1LineFeedTerminators || num + 8 != span.Length))
		{
			RejectRequestLine(span);
		}
		ReadOnlySpan<byte> readOnlySpan = span.Slice(num);
		HttpVersion httpVersion = (versionAndMethod.Version = readOnlySpan.GetKnownVersion());
		if (httpVersion == HttpVersion.Unknown)
		{
			RejectUnknownVersion(readOnlySpan);
		}
		Span<byte> startLine = MemoryMarshal.CreateSpan(ref MemoryMarshal.GetReference(span), length);
		handler.OnStartLine(versionAndMethod, targetPath, startLine);
		return true;
	}

	public bool ParseHeaders(TRequestHandler handler, ref SequenceReader<byte> reader)
	{
		while (!reader.End)
		{
			ReadOnlySpan<byte> readOnlySpan = reader.UnreadSpan;
			if (readOnlySpan.Length >= 2 && readOnlySpan[0] == 13 && readOnlySpan[1] == 10)
			{
				reader.Advance(2L);
				handler.OnHeadersComplete(endStream: false);
				return true;
			}
			bool flag = false;
			int num = readOnlySpan.IndexOfAny((byte)13, (byte)10);
			if (num >= 0)
			{
				if (readOnlySpan[num] == 13)
				{
					int num2 = num;
					reader.Advance(num2 + 1);
					bool flag2;
					byte value;
					if ((uint)readOnlySpan.Length > (uint)(num2 + 1) && readOnlySpan[num2 + 1] == 10)
					{
						readOnlySpan = readOnlySpan.Slice(0, num2);
						flag = true;
					}
					else if ((flag2 = reader.TryPeek(out value)) && value == 10)
					{
						readOnlySpan = readOnlySpan.Slice(0, readOnlySpan.Length - 1);
						flag = true;
					}
					else
					{
						if (!flag2)
						{
							reader.Rewind(num2 + 1);
							return false;
						}
						if (num2 == 0)
						{
							KestrelBadHttpRequestException.Throw(RequestRejectionReason.InvalidRequestHeadersNoCRLF);
						}
						else
						{
							RejectRequestHeader(readOnlySpan[..Math.Min(num2 + 2, readOnlySpan.Length)]);
						}
					}
					if (flag)
					{
						reader.Advance(1L);
						if (num2 == 0)
						{
							handler.OnHeadersComplete(endStream: false);
							return true;
						}
					}
				}
				else
				{
					int num3 = num;
					if (_disableHttp1LineFeedTerminators)
					{
						RejectRequestHeader(AppendEndOfLine(readOnlySpan.Slice(0, num3), lineFeedOnly: true));
					}
					reader.Advance(num3 + 1);
					readOnlySpan = readOnlySpan.Slice(0, num3);
					if (readOnlySpan.Length == 0)
					{
						handler.OnHeadersComplete(endStream: false);
						return true;
					}
				}
				if (!TryTakeSingleHeader(handler, readOnlySpan))
				{
					RejectRequestHeader(AppendEndOfLine(readOnlySpan, !flag));
				}
			}
			else
			{
				int num4 = ParseMultiSpanHeader(handler, ref reader);
				if (num4 < 0)
				{
					return false;
				}
				reader.Advance(num4);
			}
		}
		return false;
	}

	private static byte[] AppendEndOfLine(ReadOnlySpan<byte> span, bool lineFeedOnly)
	{
		byte[] array = new byte[span.Length + (lineFeedOnly ? 1 : 2)];
		span.CopyTo(array);
		array[^1] = 10;
		if (!lineFeedOnly)
		{
			array[^2] = 13;
		}
		return array;
	}

	private int ParseMultiSpanHeader(TRequestHandler handler, ref SequenceReader<byte> reader)
	{
		ReadOnlySequence<byte> unreadSequence = reader.UnreadSequence;
		SequencePosition position = unreadSequence.Start;
		unreadSequence.TryGet(ref position, out var memory);
		if (position.GetObject() == null)
		{
			return -1;
		}
		int num = -1;
		int num2 = memory.Length;
		while (unreadSequence.TryGet(ref position, out memory))
		{
			num = memory.Span.IndexOfAny((byte)13, (byte)10);
			if (num >= 0)
			{
				num2 += num;
				break;
			}
			if (position.GetObject() == null)
			{
				return -1;
			}
			num2 += memory.Length;
		}
		if (num == -1)
		{
			return -1;
		}
		if (num2 == unreadSequence.Length - 1)
		{
			if (memory.Span[num] == 13)
			{
				return -1;
			}
			if (_disableHttp1LineFeedTerminators)
			{
				RejectRequestHeader(unreadSequence.Slice(0, num2 + 1).ToSpan());
			}
		}
		ReadOnlySequence<byte> source;
		if (memory.Span[num] == 13)
		{
			num2 += 2;
			source = unreadSequence.Slice(0, num2);
		}
		else
		{
			if (_disableHttp1LineFeedTerminators)
			{
				RejectRequestHeader(unreadSequence.Slice(0, num2 + 1).ToSpan());
				return -1;
			}
			num2++;
			source = unreadSequence.Slice(0, num2);
		}
		int num3 = (_disableHttp1LineFeedTerminators ? 5 : 4);
		if (num2 < num3)
		{
			RejectRequestHeader(unreadSequence.Slice(0, num2).ToSpan());
		}
		byte[] array = null;
		Span<byte> span = ((num2 > 256) ? ((Span<byte>)(array = ArrayPool<byte>.Shared.Rent(num2))) : stackalloc byte[256]);
		Span<byte> span2 = span;
		source.CopyTo(span2);
		span2 = span2.Slice(0, num2);
		int num4 = -1;
		if (span2[span2.Length - 1] == 10)
		{
			if (span2[span2.Length - 2] == 13)
			{
				num4 = 2;
			}
			else if (!_disableHttp1LineFeedTerminators)
			{
				num4 = 1;
			}
		}
		if (num4 == -1 || !TryTakeSingleHeader(handler, span2.Slice(0, span2.Length - num4)))
		{
			RejectRequestHeader(span2);
		}
		if (array != null)
		{
			ArrayPool<byte>.Shared.Return(array);
		}
		return num2;
	}

	private static bool TryTakeSingleHeader(TRequestHandler handler, ReadOnlySpan<byte> headerLine)
	{
		int num = headerLine.IndexOfAny((byte)58, (byte)32, (byte)9);
		if ((uint)num >= (uint)headerLine.Length)
		{
			return false;
		}
		byte b = headerLine[num];
		if (num == 0)
		{
			return false;
		}
		if (b != 58)
		{
			return false;
		}
		int i = num + 1;
		if ((uint)i < (uint)headerLine.Length)
		{
			byte b2 = headerLine[i];
			if (b2 == 32 || b2 == 9)
			{
				i++;
				if ((uint)i < (uint)headerLine.Length)
				{
					switch (headerLine[i])
					{
					case 9:
					case 32:
						for (i++; i < headerLine.Length; i++)
						{
							b2 = headerLine[i];
							if (b2 != 9 && b2 != 32)
							{
								break;
							}
						}
						break;
					}
				}
			}
		}
		int num2 = headerLine.Length - 1;
		if (num2 > i)
		{
			switch (headerLine[num2])
			{
			case 9:
			case 32:
				for (num2--; num2 > i; num2--)
				{
					byte b3 = headerLine[num2];
					if (b3 != 9 && b3 != 32)
					{
						break;
					}
				}
				break;
			}
		}
		num2++;
		ref TRequestHandler reference = ref handler;
		TRequestHandler val = default;
		if (val == null)
		{
			val = reference;
			reference = ref val;
		}
		ReadOnlySpan<byte> name = headerLine.Slice(0, num);
		int num3 = i;
		ReadOnlySpan<byte> value = headerLine.Slice(num3, num2 - num3);
		reference.OnHeader(name, value);
		return true;
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private int GetUnknownMethodLength(ReadOnlySpan<byte> span)
	{
		int num = HttpCharacters.IndexOfInvalidTokenChar(span);
		if (num <= 0 || span[num] != 32)
		{
			RejectRequestLine(span);
		}
		return num;
	}

	private static bool IsTlsHandshake(ReadOnlySpan<byte> requestLine)
	{
		if (requestLine.Length >= 1)
		{
			return requestLine[0] == 22;
		}
		return false;
	}

	[StackTraceHidden]
	private void RejectRequestLine(ReadOnlySpan<byte> requestLine)
	{
		throw GetInvalidRequestException((!IsTlsHandshake(requestLine)) ? RequestRejectionReason.InvalidRequestLine : RequestRejectionReason.TlsOverHttpError, requestLine);
	}

	[StackTraceHidden]
	private void RejectRequestHeader(ReadOnlySpan<byte> headerLine)
	{
		throw GetInvalidRequestException(RequestRejectionReason.InvalidRequestHeader, headerLine);
	}

	[StackTraceHidden]
	private void RejectUnknownVersion(ReadOnlySpan<byte> version)
	{
		throw GetInvalidRequestException(RequestRejectionReason.UnrecognizedHTTPVersion, version.Slice(0, version.Length - 1));
	}

	[MethodImpl(MethodImplOptions.NoInlining)]
	private Microsoft.AspNetCore.Http.BadHttpRequestException GetInvalidRequestException(RequestRejectionReason reason, ReadOnlySpan<byte> headerLine)
	{
		return KestrelBadHttpRequestException.GetException(reason, _showErrorDetails ? headerLine.GetAsciiStringEscaped(128) : string.Empty);
	}
}
