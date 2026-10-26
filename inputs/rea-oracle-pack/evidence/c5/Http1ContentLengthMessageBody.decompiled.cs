using System;
using System.Buffers;
using System.Diagnostics;
using System.Globalization;
using System.IO.Pipelines;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Connections;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;

internal sealed class Http1ContentLengthMessageBody : Http1MessageBody
{
	[StructLayout(LayoutKind.Auto)]
	[CompilerGenerated]
	private struct <ReadAsyncInternal>d__9 : IAsyncStateMachine
	{
		public int <>1__state;

		public PoolingAsyncValueTaskMethodBuilder<ReadResult> <>t__builder;

		public Http1ContentLengthMessageBody <>4__this;

		public CancellationToken cancellationToken;

		private TaskAwaiter <>u__1;

		private ValueTaskAwaiter<ReadResult> <>u__2;

		private void MoveNext()
		{
			int num = <>1__state;
			Http1ContentLengthMessageBody CS$<>8__locals28 = <>4__this;
			ReadResult result;
			try
			{
				TaskAwaiter awaiter;
				if (num == 0)
				{
					awaiter = <>u__1;
					<>u__1 = default;
					num = (<>1__state = -1);
					goto IL_00be;
				}
				if (num == 1)
				{
					goto IL_00c6;
				}
				CS$<>8__locals28.VerifyIsNotReading();
				if (!CS$<>8__locals28._readCompleted)
				{
					if (CS$<>8__locals28._context.RequestTimedOut)
					{
						KestrelBadHttpRequestException.Throw(RequestRejectionReason.RequestBodyTimeout);
					}
					awaiter = CS$<>8__locals28.TryStartAsync().GetAwaiter();
					if (!awaiter.IsCompleted)
					{
						num = (<>1__state = 0);
						<>u__1 = awaiter;
						<>t__builder.AwaitUnsafeOnCompleted(ref awaiter, ref this);
						return;
					}
					goto IL_00be;
				}
				CS$<>8__locals28._isReading = true;
				result = new ReadResult(CS$<>8__locals28._readResult.Buffer, Interlocked.Exchange(ref CS$<>8__locals28._userCanceled, 0) == 1, isCompleted: true);
				goto end_IL_000e;
				IL_00be:
				awaiter.GetResult();
				goto IL_00c6;
				IL_00c6:
				while (true)
				{
					try
					{
						ValueTaskAwaiter<ReadResult> awaiter2;
						if (num != 1)
						{
							ValueTask<ReadResult> readAwaitable = CS$<>8__locals28._context.Input.ReadAsync(cancellationToken);
							CS$<>8__locals28._isReading = true;
							awaiter2 = CS$<>8__locals28.StartTimingReadAsync(readAwaitable, cancellationToken).GetAwaiter();
							if (!awaiter2.IsCompleted)
							{
								num = (<>1__state = 1);
								<>u__2 = awaiter2;
								<>t__builder.AwaitUnsafeOnCompleted(ref awaiter2, ref this);
								return;
							}
						}
						else
						{
							awaiter2 = <>u__2;
							<>u__2 = default;
							num = (<>1__state = -1);
						}
						ReadResult result2 = awaiter2.GetResult();
						CS$<>8__locals28._readResult = result2;
					}
					catch (ConnectionAbortedException innerException)
					{
						CS$<>8__locals28._isReading = false;
						throw new TaskCanceledException("The request was aborted", innerException);
					}
					if (CS$<>8__locals28._context.RequestTimedOut)
					{
						ResetReadingState();
						KestrelBadHttpRequestException.Throw(RequestRejectionReason.RequestBodyTimeout);
					}
					if (CS$<>8__locals28._readResult.IsCompleted)
					{
						ResetReadingState();
						CS$<>8__locals28.ThrowUnexpectedEndOfRequestContent();
					}
					if (!CS$<>8__locals28._readResult.IsCanceled || Interlocked.Exchange(ref CS$<>8__locals28._userCanceled, 0) == 1 || CS$<>8__locals28._cannotResetInputPipe)
					{
						break;
					}
					ResetReadingState();
				}
				long bytesInReadResult = CS$<>8__locals28.CreateReadResultFromConnectionReadResult();
				CS$<>8__locals28.StopTimingRead(bytesInReadResult);
				if (CS$<>8__locals28._readResult.IsCompleted)
				{
					CS$<>8__locals28.TryStop();
				}
				result = CS$<>8__locals28._readResult;
				end_IL_000e:;
			}
			catch (Exception exception)
			{
				<>1__state = -2;
				<>t__builder.SetException(exception);
				return;
			}
			<>1__state = -2;
			<>t__builder.SetResult(result);
			void ResetReadingState()
			{
				CS$<>8__locals28.StopTimingRead(0L);
				if (!CS$<>8__locals28._cannotResetInputPipe)
				{
					CS$<>8__locals28._isReading = false;
					CS$<>8__locals28._context.Input.AdvanceTo(CS$<>8__locals28._readResult.Buffer.Start);
				}
			}
		}

		void IAsyncStateMachine.MoveNext()
		{
			//ILSpy generated this explicit interface implementation from .override directive in MoveNext
			this.MoveNext();
		}

		[DebuggerHidden]
		private void SetStateMachine(IAsyncStateMachine stateMachine)
		{
			<>t__builder.SetStateMachine(stateMachine);
		}

		void IAsyncStateMachine.SetStateMachine(IAsyncStateMachine stateMachine)
		{
			//ILSpy generated this explicit interface implementation from .override directive in SetStateMachine
			this.SetStateMachine(stateMachine);
		}
	}

	private ReadResult _readResult;

	private readonly long _contentLength;

	private long _unexaminedInputLength;

	private bool _readCompleted;

	private bool _isReading;

	private int _userCanceled;

	private bool _finalAdvanceCalled;

	private bool _cannotResetInputPipe;

	public Http1ContentLengthMessageBody(Http1Connection context, long contentLength, bool keepAlive)
		: base(context, keepAlive)
	{
		_contentLength = contentLength;
		_unexaminedInputLength = contentLength;
	}

	[AsyncStateMachine(typeof(<ReadAsyncInternal>d__9))]
	[AsyncMethodBuilder(typeof(PoolingAsyncValueTaskMethodBuilder<>))]
	public override ValueTask<ReadResult> ReadAsyncInternal(CancellationToken cancellationToken = default(CancellationToken))
	{
		<ReadAsyncInternal>d__9 stateMachine = default;
		stateMachine.<>t__builder = PoolingAsyncValueTaskMethodBuilder<ReadResult>.Create();
		stateMachine.<>4__this = this;
		stateMachine.cancellationToken = cancellationToken;
		stateMachine.<>1__state = -1;
		stateMachine.<>t__builder.Start(ref stateMachine);
		return stateMachine.<>t__builder.Task;
	}

	public override bool TryReadInternal(out ReadResult readResult)
	{
		VerifyIsNotReading();
		if (_readCompleted)
		{
			_isReading = true;
			readResult = new ReadResult(_readResult.Buffer, Interlocked.Exchange(ref _userCanceled, 0) == 1, isCompleted: true);
			return true;
		}
		if (_context.RequestTimedOut)
		{
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.RequestBodyTimeout);
		}
		TryStartAsync();
		while (true)
		{
			if (!_context.Input.TryRead(out _readResult))
			{
				readResult = default;
				return false;
			}
			if (!_readResult.IsCanceled || Interlocked.Exchange(ref _userCanceled, 0) == 1 || _cannotResetInputPipe)
			{
				break;
			}
			_context.Input.AdvanceTo(_readResult.Buffer.Start);
		}
		if (_readResult.IsCompleted)
		{
			if (_cannotResetInputPipe)
			{
				_isReading = true;
			}
			else
			{
				_context.Input.AdvanceTo(_readResult.Buffer.Start);
			}
			ThrowUnexpectedEndOfRequestContent();
		}
		long bytesInReadResult = CreateReadResultFromConnectionReadResult();
		CountBytesRead(bytesInReadResult);
		_isReading = true;
		readResult = _readResult;
		if (readResult.IsCompleted)
		{
			TryStop();
		}
		return true;
	}

	private long CreateReadResultFromConnectionReadResult()
	{
		long length = _readResult.Buffer.Length;
		long num = _unexaminedInputLength + _examinedUnconsumedBytes;
		if (length < num)
		{
			return length;
		}
		_readCompleted = true;
		_readResult = new ReadResult(_readResult.Buffer.Slice(0L, num), _readResult.IsCanceled, isCompleted: true);
		return num;
	}

	public override void AdvanceTo(SequencePosition consumed, SequencePosition examined)
	{
		if (!_isReading)
		{
			throw new InvalidOperationException("No reading operation to complete.");
		}
		_isReading = false;
		if (_readCompleted)
		{
			ReadOnlySequence<byte> buffer = _readResult.Buffer.Slice(consumed, _readResult.Buffer.End);
			if (!_finalAdvanceCalled && buffer.IsEmpty)
			{
				_readResult = new ReadResult(default, isCanceled: false, isCompleted: true);
				_context.Input.AdvanceTo(consumed);
				_finalAdvanceCalled = true;
				_context.OnTrailersComplete();
			}
			else
			{
				_readResult = new ReadResult(buffer, isCanceled: false, isCompleted: true);
			}
		}
		else
		{
			_cannotResetInputPipe = !consumed.Equals(examined);
			_unexaminedInputLength -= TrackConsumedAndExaminedBytes(_readResult, consumed, examined);
			_context.Input.AdvanceTo(consumed, examined);
		}
	}

	protected override void OnReadStarting()
	{
		long? maxRequestBodySize = _context.MaxRequestBodySize;
		if (_contentLength > maxRequestBodySize)
		{
			_context.DisableKeepAlive(ConnectionEndReason.MaxRequestBodySizeExceeded);
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.RequestBodyTooLarge, maxRequestBodySize.GetValueOrDefault().ToString(CultureInfo.InvariantCulture));
		}
	}

	public override void CancelPendingRead()
	{
		Interlocked.Exchange(ref _userCanceled, 1);
		_context.Input.CancelPendingRead();
	}

	[StackTraceHidden]
	private void VerifyIsNotReading()
	{
		if (!_isReading)
		{
			return;
		}
		if (_cannotResetInputPipe)
		{
			if (_readResult.IsCompleted)
			{
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.UnexpectedEndOfRequestContent);
			}
			if (_context.RequestTimedOut)
			{
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.RequestBodyTimeout);
			}
		}
		throw new InvalidOperationException("Reading is already in progress.");
	}
}
