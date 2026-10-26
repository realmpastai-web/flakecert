using System.Buffers;
using System.Diagnostics.CodeAnalysis;
using System.Net.Http.HPack;
using System.Numerics;

namespace System.Net.Http.QPack;

internal sealed class QPackDecoder : IDisposable
{
	private enum State
	{
		RequiredInsertCount,
		RequiredInsertCountContinue,
		Base,
		BaseContinue,
		CompressedHeaders,
		HeaderFieldIndex,
		HeaderNameIndex,
		HeaderNameLength,
		HeaderName,
		HeaderValueLength,
		HeaderValueLengthContinue,
		HeaderValue,
		PostBaseIndex,
		HeaderNameIndexPostBase
	}

	private const int RequiredInsertCountPrefix = 8;

	private const int BaseMask = 128;

	private const int BasePrefix = 7;

	private const byte IndexedHeaderStaticMask = 64;

	private const byte IndexedHeaderStaticRepresentation = 64;

	private const byte IndexedHeaderFieldPrefixMask = 63;

	private const int IndexedHeaderFieldPrefix = 6;

	private const byte PostBaseIndexMask = 240;

	private const int PostBaseIndexPrefix = 4;

	private const byte LiteralHeaderFieldStaticMask = 16;

	private const byte LiteralHeaderFieldPrefixMask = 15;

	private const int LiteralHeaderFieldPrefix = 4;

	private const byte LiteralHeaderFieldPostBasePrefixMask = 7;

	private const int LiteralHeaderFieldPostBasePrefix = 3;

	private const byte LiteralHeaderFieldWithoutNameReferenceHuffmanMask = 8;

	private const byte LiteralHeaderFieldWithoutNameReferencePrefixMask = 7;

	private const int LiteralHeaderFieldWithoutNameReferencePrefix = 3;

	private const int StringLengthPrefix = 7;

	private const byte HuffmanMask = 128;

	private const int HeaderStaticIndexUnset = -1;

	private readonly int _maxHeadersLength;

	private State _state;

	private bool _huffman;

	private byte[] _headerName;

	private int _headerStaticIndex;

	private int _headerNameLength;

	private int _headerValueLength;

	private int _stringLength;

	private int _stringIndex;

	private IntegerDecoder _integerDecoder;

	private byte[] _stringOctets;

	private byte[] _headerNameOctets;

	private byte[] _headerValueOctets;

	private (int start, int length)? _headerNameRange;

	private (int start, int length)? _headerValueRange;

	private static ArrayPool<byte> Pool => ArrayPool<byte>.Shared;

	public QPackDecoder(int maxHeadersLength)
	{
		_maxHeadersLength = maxHeadersLength;
		_headerStaticIndex = -1;
	}

	public void Dispose()
	{
		if (_stringOctets != null)
		{
			Pool.Return(_stringOctets);
			_stringOctets = null;
		}
		if (_headerNameOctets != null)
		{
			Pool.Return(_headerNameOctets);
			_headerNameOctets = null;
		}
		if (_headerValueOctets != null)
		{
			Pool.Return(_headerValueOctets);
			_headerValueOctets = null;
		}
	}

	public void Reset()
	{
		_state = State.RequiredInsertCount;
	}

	public void Decode(in ReadOnlySequence<byte> data, bool endHeaders, IHttpStreamHeadersHandler handler)
	{
		foreach (ReadOnlyMemory<byte> datum in data)
		{
			DecodeInternal(datum.Span, handler);
		}
		CheckIncompleteHeaderBlock(endHeaders);
	}

	public void Decode(ReadOnlySpan<byte> data, bool endHeaders, IHttpStreamHeadersHandler handler)
	{
		DecodeInternal(data, handler);
		CheckIncompleteHeaderBlock(endHeaders);
	}

	private void DecodeInternal(ReadOnlySpan<byte> data, IHttpStreamHeadersHandler handler)
	{
		int currentIndex = 0;
		do
		{
			switch (_state)
			{
			case State.RequiredInsertCount:
				ParseRequiredInsertCount(data, ref currentIndex, handler);
				break;
			case State.RequiredInsertCountContinue:
				ParseRequiredInsertCountContinue(data, ref currentIndex, handler);
				break;
			case State.Base:
				ParseBase(data, ref currentIndex, handler);
				break;
			case State.BaseContinue:
				ParseBaseContinue(data, ref currentIndex, handler);
				break;
			case State.CompressedHeaders:
				ParseCompressedHeaders(data, ref currentIndex, handler);
				break;
			case State.HeaderFieldIndex:
				ParseHeaderFieldIndex(data, ref currentIndex, handler);
				break;
			case State.HeaderNameIndex:
				ParseHeaderNameIndex(data, ref currentIndex, handler);
				break;
			case State.HeaderNameLength:
				ParseHeaderNameLength(data, ref currentIndex, handler);
				break;
			case State.HeaderName:
				ParseHeaderName(data, ref currentIndex, handler);
				break;
			case State.HeaderValueLength:
				ParseHeaderValueLength(data, ref currentIndex, handler);
				break;
			case State.HeaderValueLengthContinue:
				ParseHeaderValueLengthContinue(data, ref currentIndex, handler);
				break;
			case State.HeaderValue:
				ParseHeaderValue(data, ref currentIndex, handler);
				break;
			case State.PostBaseIndex:
				ParsePostBaseIndex(data, ref currentIndex);
				break;
			case State.HeaderNameIndexPostBase:
				ParseHeaderNameIndexPostBase(data, ref currentIndex);
				break;
			default:
				throw new NotImplementedException(_state.ToString());
			}
		}
		while (currentIndex < data.Length);
		if (_headerNameRange.HasValue)
		{
			EnsureStringCapacity(ref _headerNameOctets, _headerNameLength, 0);
			_headerName = _headerNameOctets;
			data.Slice(_headerNameRange.GetValueOrDefault().start, _headerNameRange.GetValueOrDefault().length).CopyTo(_headerName);
			_headerNameRange = null;
		}
	}

	private void ParseHeaderNameIndexPostBase(ReadOnlySpan<byte> data, ref int currentIndex)
	{
		if (TryDecodeInteger(data, ref currentIndex, out var result))
		{
			OnIndexedHeaderNamePostBase(result);
		}
	}

	private void ParsePostBaseIndex(ReadOnlySpan<byte> data, ref int currentIndex)
	{
		if (TryDecodeInteger(data, ref currentIndex, out var _))
		{
			OnPostBaseIndex();
		}
	}

	private void ParseHeaderNameLength(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (TryDecodeInteger(data, ref currentIndex, out var result))
		{
			if (result == 0)
			{
				throw new QPackDecodingException(SR.Format(SR.net_http_invalid_header_name, ""));
			}
			OnStringLength(result, State.HeaderName);
			ParseHeaderName(data, ref currentIndex, handler);
		}
	}

	private void ParseHeaderName(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		int num = Math.Min(_stringLength - _stringIndex, data.Length - currentIndex);
		if (num == _stringLength && !_huffman)
		{
			_headerNameRange = (currentIndex, num);
			_headerNameLength = _stringLength;
			currentIndex += num;
			_state = State.HeaderValueLength;
			ParseHeaderValueLength(data, ref currentIndex, handler);
		}
		else if (num != 0)
		{
			EnsureStringCapacity(ref _stringOctets, _stringIndex + num, _stringIndex);
			data.Slice(currentIndex, num).CopyTo(_stringOctets.AsSpan(_stringIndex));
			_stringIndex += num;
			currentIndex += num;
			if (_stringIndex == _stringLength)
			{
				OnString(State.HeaderValueLength);
				ParseHeaderValueLength(data, ref currentIndex, handler);
			}
		}
	}

	private void ParseHeaderFieldIndex(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (TryDecodeInteger(data, ref currentIndex, out var result))
		{
			OnIndexedHeaderField(result, handler);
		}
	}

	private void ParseHeaderNameIndex(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (TryDecodeInteger(data, ref currentIndex, out var result))
		{
			OnIndexedHeaderName(result);
			ParseHeaderValueLength(data, ref currentIndex, handler);
		}
	}

	private void ParseHeaderValueLength(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (currentIndex >= data.Length)
		{
			return;
		}
		byte b = data[currentIndex++];
		_huffman = IsHuffmanEncoded(b);
		if (_integerDecoder.BeginTryDecode((byte)(b & -129), 7, out var result))
		{
			OnStringLength(result, State.HeaderValue);
			if (result == 0)
			{
				_state = State.CompressedHeaders;
				ProcessHeaderValue(data, handler);
			}
			else
			{
				ParseHeaderValue(data, ref currentIndex, handler);
			}
		}
		else
		{
			_state = State.HeaderValueLengthContinue;
			ParseHeaderValueLengthContinue(data, ref currentIndex, handler);
		}
	}

	private void ParseHeaderValue(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		int num = Math.Min(_stringLength - _stringIndex, data.Length - currentIndex);
		if (num == _stringLength && !_huffman)
		{
			_headerValueRange = (currentIndex, num);
			currentIndex += num;
			_state = State.CompressedHeaders;
			ProcessHeaderValue(data, handler);
		}
		else if (num != 0)
		{
			EnsureStringCapacity(ref _stringOctets, _stringIndex + num, _stringIndex);
			data.Slice(currentIndex, num).CopyTo(_stringOctets.AsSpan(_stringIndex));
			_stringIndex += num;
			currentIndex += num;
			if (_stringIndex == _stringLength)
			{
				OnString(State.CompressedHeaders);
				ProcessHeaderValue(data, handler);
			}
		}
	}

	private void ParseHeaderValueLengthContinue(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (TryDecodeInteger(data, ref currentIndex, out var result))
		{
			if (result == 0)
			{
				_state = State.CompressedHeaders;
				ProcessHeaderValue(data, handler);
			}
			else
			{
				OnStringLength(result, State.HeaderValue);
				ParseHeaderValue(data, ref currentIndex, handler);
			}
		}
	}

	private void ParseCompressedHeaders(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (currentIndex >= data.Length)
		{
			return;
		}
		byte b = data[currentIndex++];
		int result;
		switch (BitOperations.LeadingZeroCount(b))
		{
		case 24:
		{
			int num = 0x3F & b;
			if ((b & 0x40) != 64)
			{
				ThrowDynamicTableNotSupported();
			}
			if (_integerDecoder.BeginTryDecode((byte)num, 6, out result))
			{
				OnIndexedHeaderField(result, handler);
				break;
			}
			_state = State.HeaderFieldIndex;
			ParseHeaderFieldIndex(data, ref currentIndex, handler);
			break;
		}
		case 25:
		{
			if ((0x10 & b) != 16)
			{
				ThrowDynamicTableNotSupported();
			}
			int num = b & 0xF;
			if (_integerDecoder.BeginTryDecode((byte)num, 4, out result))
			{
				OnIndexedHeaderName(result);
				ParseHeaderValueLength(data, ref currentIndex, handler);
			}
			else
			{
				_state = State.HeaderNameIndex;
				ParseHeaderNameIndex(data, ref currentIndex, handler);
			}
			break;
		}
		case 26:
		{
			_huffman = (b & 8) != 0;
			int num = b & 7;
			if (_integerDecoder.BeginTryDecode((byte)num, 3, out result))
			{
				if (result == 0)
				{
					throw new QPackDecodingException(SR.Format(SR.net_http_invalid_header_name, ""));
				}
				OnStringLength(result, State.HeaderName);
				ParseHeaderName(data, ref currentIndex, handler);
			}
			else
			{
				_state = State.HeaderNameLength;
				ParseHeaderNameLength(data, ref currentIndex, handler);
			}
			break;
		}
		case 27:
		{
			int num = -241 & b;
			if (_integerDecoder.BeginTryDecode((byte)num, 4, out var _))
			{
				OnPostBaseIndex();
				break;
			}
			_state = State.PostBaseIndex;
			ParsePostBaseIndex(data, ref currentIndex);
			break;
		}
		default:
		{
			int num = b & 7;
			if (_integerDecoder.BeginTryDecode((byte)num, 3, out result))
			{
				OnIndexedHeaderNamePostBase(result);
				break;
			}
			_state = State.HeaderNameIndexPostBase;
			ParseHeaderNameIndexPostBase(data, ref currentIndex);
			break;
		}
		}
	}

	private void ParseRequiredInsertCountContinue(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (TryDecodeInteger(data, ref currentIndex, out var result))
		{
			OnRequiredInsertCount(result);
			ParseBase(data, ref currentIndex, handler);
		}
	}

	private void ParseBase(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (currentIndex < data.Length)
		{
			byte b = data[currentIndex++];
			int num = -129 & b;
			if (_integerDecoder.BeginTryDecode((byte)num, 7, out var result))
			{
				OnBase(result);
				ParseCompressedHeaders(data, ref currentIndex, handler);
			}
			else
			{
				_state = State.BaseContinue;
				ParseBaseContinue(data, ref currentIndex, handler);
			}
		}
	}

	private void ParseBaseContinue(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (TryDecodeInteger(data, ref currentIndex, out var result))
		{
			OnBase(result);
			ParseCompressedHeaders(data, ref currentIndex, handler);
		}
	}

	private void ParseRequiredInsertCount(ReadOnlySpan<byte> data, ref int currentIndex, IHttpStreamHeadersHandler handler)
	{
		if (currentIndex < data.Length)
		{
			byte b = data[currentIndex++];
			if (_integerDecoder.BeginTryDecode(b, 8, out var result))
			{
				OnRequiredInsertCount(result);
				ParseBase(data, ref currentIndex, handler);
			}
			else
			{
				_state = State.RequiredInsertCountContinue;
				ParseRequiredInsertCountContinue(data, ref currentIndex, handler);
			}
		}
	}

	private void CheckIncompleteHeaderBlock(bool endHeaders)
	{
		if (endHeaders && _state != State.CompressedHeaders)
		{
			throw new QPackDecodingException(SR.net_http_hpack_incomplete_header_block);
		}
	}

	private void ProcessHeaderValue(ReadOnlySpan<byte> data, IHttpStreamHeadersHandler handler)
	{
		ReadOnlySpan<byte> value = ((!_headerValueRange.HasValue) ? ((ReadOnlySpan<byte>)_headerValueOctets.AsSpan(0, _headerValueLength)) : data.Slice(_headerValueRange.GetValueOrDefault().start, _headerValueRange.GetValueOrDefault().length));
		if (_headerStaticIndex != -1)
		{
			handler.OnStaticIndexedHeader(_headerStaticIndex, value);
		}
		else
		{
			ReadOnlySpan<byte> name = ((!_headerNameRange.HasValue) ? ((ReadOnlySpan<byte>)_headerName.AsSpan(0, _headerNameLength)) : data.Slice(_headerNameRange.GetValueOrDefault().start, _headerNameRange.GetValueOrDefault().length));
			handler.OnHeader(name, value);
		}
		_headerStaticIndex = -1;
		_headerNameRange = null;
		_headerNameLength = 0;
		_headerValueRange = null;
		_headerValueLength = 0;
	}

	private void OnStringLength(int length, State nextState)
	{
		if (length > _maxHeadersLength)
		{
			throw new QPackDecodingException(SR.Format(SR.net_http_headers_exceeded_length, _maxHeadersLength));
		}
		_stringLength = length;
		_stringIndex = 0;
		_state = nextState;
	}

	private void OnString(State nextState)
	{
		try
		{
			if (_state == State.HeaderName)
			{
				_headerNameLength = Decode(ref _headerNameOctets);
				_headerName = _headerNameOctets;
			}
			else
			{
				_headerValueLength = Decode(ref _headerValueOctets);
			}
		}
		catch (HuffmanDecodingException innerException)
		{
			throw new QPackDecodingException(SR.net_http_hpack_huffman_decode_failed, innerException);
		}
		_state = nextState;
		int Decode(ref byte[] dst)
		{
			EnsureStringCapacity(ref dst, _stringLength, 0);
			if (_huffman)
			{
				return Huffman.Decode(new ReadOnlySpan<byte>(_stringOctets, 0, _stringLength), ref dst);
			}
			Buffer.BlockCopy(_stringOctets, 0, dst, 0, _stringLength);
			return _stringLength;
		}
	}

	private static void EnsureStringCapacity([NotNull] ref byte[] buffer, int requiredLength, int existingLength)
	{
		if (buffer == null)
		{
			buffer = Pool.Rent(requiredLength);
		}
		else if (buffer.Length < requiredLength)
		{
			byte[] array = Pool.Rent(requiredLength);
			if (existingLength > 0)
			{
				buffer.AsMemory(0, existingLength).CopyTo(array);
			}
			Pool.Return(buffer);
			buffer = array;
		}
	}

	private bool TryDecodeInteger(ReadOnlySpan<byte> data, ref int currentIndex, out int result)
	{
		while (currentIndex < data.Length)
		{
			if (_integerDecoder.TryDecode(data[currentIndex], out result))
			{
				currentIndex++;
				return true;
			}
			currentIndex++;
		}
		result = 0;
		return false;
	}

	private static bool IsHuffmanEncoded(byte b)
	{
		return (b & 0x80) != 0;
	}

	private void OnIndexedHeaderName(int index)
	{
		_headerStaticIndex = index;
		_state = State.HeaderValueLength;
	}

	private static void OnIndexedHeaderNamePostBase(int _)
	{
		ThrowDynamicTableNotSupported();
	}

	private static void OnPostBaseIndex()
	{
		ThrowDynamicTableNotSupported();
	}

	private void OnBase(int deltaBase)
	{
		if (deltaBase != 0)
		{
			ThrowDynamicTableNotSupported();
		}
		_state = State.CompressedHeaders;
	}

	private void OnRequiredInsertCount(int requiredInsertCount)
	{
		if (requiredInsertCount != 0)
		{
			ThrowDynamicTableNotSupported();
		}
		_state = State.Base;
	}

	private void OnIndexedHeaderField(int index, IHttpStreamHeadersHandler handler)
	{
		handler.OnStaticIndexedHeader(index);
		_state = State.CompressedHeaders;
	}

	private static void ThrowDynamicTableNotSupported()
	{
		throw new QPackDecodingException(SR.net_http_qpack_no_dynamic_table);
	}
}
