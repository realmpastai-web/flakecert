using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO.Pipelines;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Connections;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure;
using Microsoft.Extensions.Primitives;
using Microsoft.Net.Http.Headers;

namespace Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http;

internal abstract class Http1MessageBody : MessageBody
{
	private static readonly bool ContinueProcessingAfterCLTE = AppContext.TryGetSwitch("Microsoft.AspNetCore.Server.Kestrel.AllowKeepAliveAfterCLTE", out var isEnabled) & isEnabled;

	protected readonly Http1Connection _context;

	private bool _readerCompleted;

	protected Http1MessageBody(Http1Connection context, bool keepAlive)
		: base(context)
	{
		_context = context;
		RequestKeepAlive = keepAlive;
	}

	public override ValueTask<ReadResult> ReadAsync(CancellationToken cancellationToken = default(CancellationToken))
	{
		ThrowIfReaderCompleted();
		return ReadAsyncInternal(cancellationToken);
	}

	public abstract ValueTask<ReadResult> ReadAsyncInternal(CancellationToken cancellationToken = default(CancellationToken));

	public override bool TryRead(out ReadResult readResult)
	{
		ThrowIfReaderCompleted();
		return TryReadInternal(out readResult);
	}

	public abstract bool TryReadInternal(out ReadResult readResult);

	public override void Complete(Exception? exception)
	{
		_readerCompleted = true;
		_context.ReportApplicationError(exception);
	}

	protected override Task OnConsumeAsync()
	{
		try
		{
			ReadResult readResult;
			while (TryReadInternal(out readResult))
			{
				AdvanceTo(readResult.Buffer.End);
				if (readResult.IsCompleted)
				{
					return Task.CompletedTask;
				}
			}
		}
		catch (Microsoft.AspNetCore.Http.BadHttpRequestException badRequestState)
		{
			_context.SetBadRequestState(badRequestState);
			return Task.CompletedTask;
		}
		catch (InvalidOperationException ex)
		{
			Log.RequestBodyDrainBodyReaderInvalidState(_context.ConnectionIdFeature, _context.TraceIdentifier, ex);
			_context.StopProcessingNextRequest(ConnectionEndReason.InvalidBodyReaderState);
			return Task.CompletedTask;
		}
		return OnConsumeAsyncAwaited();
	}

	protected async Task OnConsumeAsyncAwaited()
	{
		Log.RequestBodyNotEntirelyRead(_context.ConnectionIdFeature, _context.TraceIdentifier);
		_context.TimeoutControl.SetTimeout(Constants.RequestBodyDrainTimeout, TimeoutReason.RequestBodyDrain);
		try
		{
			ReadResult readResult;
			do
			{
				readResult = await ReadAsyncInternal();
				AdvanceTo(readResult.Buffer.End);
			}
			while (!readResult.IsCompleted);
		}
		catch (Microsoft.AspNetCore.Http.BadHttpRequestException badRequestState)
		{
			_context.SetBadRequestState(badRequestState);
		}
		catch (OperationCanceledException ex) when (ex is ConnectionAbortedException || ex is TaskCanceledException)
		{
			Log.RequestBodyDrainTimedOut(_context.ConnectionIdFeature, _context.TraceIdentifier);
		}
		catch (InvalidOperationException ex2)
		{
			Log.RequestBodyDrainBodyReaderInvalidState(_context.ConnectionIdFeature, _context.TraceIdentifier, ex2);
			_context.StopProcessingNextRequest(ConnectionEndReason.InvalidBodyReaderState);
		}
		finally
		{
			_context.TimeoutControl.CancelTimeout();
		}
	}

	protected override void OnObservedBytesExceedMaxRequestBodySize(long maxRequestBodySize)
	{
		_context.DisableKeepAlive(ConnectionEndReason.MaxRequestBodySizeExceeded);
		KestrelBadHttpRequestException.Throw(RequestRejectionReason.RequestBodyTooLarge, maxRequestBodySize.ToString(CultureInfo.InvariantCulture));
	}

	public static MessageBody For(HttpVersion httpVersion, HttpRequestHeaders headers, Http1Connection context)
	{
		bool flag = httpVersion != HttpVersion.Http10;
		bool flag2 = false;
		if (headers.HasConnection)
		{
			ConnectionOptions connectionOptions = HttpHeaders.ParseConnection(headers);
			flag2 = (connectionOptions & ConnectionOptions.Upgrade) != 0;
			flag = (flag || (connectionOptions & ConnectionOptions.KeepAlive) != 0) && (connectionOptions & ConnectionOptions.Close) == 0;
		}
		if (flag2 && headers.ContentLength.GetValueOrDefault() == 0L && headers.HeaderTransferEncoding.Count == 0)
		{
			context.OnTrailersComplete();
			return new Http1UpgradeMessageBody(context, flag);
		}
		if (headers.HasTransferEncoding)
		{
			StringValues headerTransferEncoding = headers.HeaderTransferEncoding;
			if (HttpHeaders.GetFinalTransferCoding(headerTransferEncoding) != TransferCoding.Chunked)
			{
				KestrelBadHttpRequestException.Throw(RequestRejectionReason.FinalTransferCodingNotChunked, headerTransferEncoding);
			}
			if (headers.ContentLength.HasValue)
			{
				((IDictionary<string, StringValues>)headers).Add("X-Content-Length", ((IHeaderDictionary)headers)[HeaderNames.ContentLength]);
				headers.ContentLength = null;
				if (!ContinueProcessingAfterCLTE)
				{
					flag = false;
				}
			}
			return new Http1ChunkedEncodingMessageBody(context, flag);
		}
		if (headers.ContentLength.HasValue)
		{
			long value = headers.ContentLength.Value;
			if (value == 0L)
			{
				if (!flag)
				{
					return MessageBody.ZeroContentLengthClose;
				}
				return MessageBody.ZeroContentLengthKeepAlive;
			}
			return new Http1ContentLengthMessageBody(context, value, flag);
		}
		if (httpVersion == HttpVersion.Http10 && (context.Method == HttpMethod.Post || context.Method == HttpMethod.Put))
		{
			KestrelMetrics.AddConnectionEndReason(context.MetricsContext, ConnectionEndReason.InvalidRequestHeaders);
			KestrelBadHttpRequestException.Throw(RequestRejectionReason.LengthRequiredHttp10, context.Method);
		}
		context.OnTrailersComplete();
		if (!flag)
		{
			return MessageBody.ZeroContentLengthClose;
		}
		return MessageBody.ZeroContentLengthKeepAlive;
	}

	[StackTraceHidden]
	protected void ThrowIfReaderCompleted()
	{
		if (_readerCompleted)
		{
			throw new InvalidOperationException("Reading is not allowed after the reader was completed.");
		}
	}

	[StackTraceHidden]
	protected void ThrowUnexpectedEndOfRequestContent()
	{
		KestrelMetrics.AddConnectionEndReason(_context.MetricsContext, ConnectionEndReason.UnexpectedEndOfRequestContent);
		((IHttpOutputAborter)_context).OnInputOrOutputCompleted();
		KestrelBadHttpRequestException.Throw(RequestRejectionReason.UnexpectedEndOfRequestContent);
	}
}
