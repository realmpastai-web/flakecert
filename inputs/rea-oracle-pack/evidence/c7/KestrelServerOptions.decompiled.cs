using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Certificates.Generation;
using Microsoft.AspNetCore.Connections;
using Microsoft.AspNetCore.Server.Kestrel.Core.Internal;
using Microsoft.AspNetCore.Server.Kestrel.Https;
using Microsoft.AspNetCore.Server.Kestrel.Https.Internal;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Microsoft.AspNetCore.Server.Kestrel.Core;

public class KestrelServerOptions
{
	internal const string DisableHttp1LineFeedTerminatorsSwitchKey = "Microsoft.AspNetCore.Server.Kestrel.DisableHttp1LineFeedTerminators";

	private const string FinOnErrorSwitch = "Microsoft.AspNetCore.Server.Kestrel.FinOnError";

	internal const string CertificateFileWatchingSwitch = "Microsoft.AspNetCore.Server.Kestrel.DisableCertificateFileWatching";

	private static readonly bool _finOnError;

	private static readonly bool _disableCertificateFileWatching;

	internal static readonly Func<string, Encoding?> DefaultHeaderEncodingSelector;

	private Func<string, Encoding> _requestHeaderEncodingSelector = DefaultHeaderEncodingSelector;

	private Func<string, Encoding> _responseHeaderEncodingSelector = DefaultHeaderEncodingSelector;

	private bool? _enableWebTransportAndH3Datagrams;

	private bool? _disableHttp1LineFeedTerminators;

	internal bool FinOnError { get; set; } = _finOnError;

	public bool AllowHostHeaderOverride { get; set; }

	internal List<ListenOptions> CodeBackedListenOptions { get; } = new List<ListenOptions>();

	internal List<ListenOptions> ConfigurationBackedListenOptions { get; } = new List<ListenOptions>();

	internal List<ListenOptions> OptionsInUse { get; } = new List<ListenOptions>();

	public bool AddServerHeader { get; set; } = true;

	public bool AllowResponseHeaderCompression { get; set; } = true;

	public bool AllowSynchronousIO { get; set; }

	public bool AllowAlternateSchemes { get; set; }

	public bool DisableStringReuse { get; set; }

	[Obsolete("This property is obsolete and will be removed in a future version. It no longer has any impact on runtime behavior. Use ListenOptions.DisableAltSvcHeader to configure \"Alt-Svc\" behavior.", true)]
	public bool EnableAltSvc { get; set; }

	public Func<string, Encoding?> RequestHeaderEncodingSelector
	{
		get
		{
			return _requestHeaderEncodingSelector;
		}
		set
		{
			_requestHeaderEncodingSelector = value ?? throw new ArgumentNullException("value");
		}
	}

	public Func<string, Encoding?> ResponseHeaderEncodingSelector
	{
		get
		{
			return _responseHeaderEncodingSelector;
		}
		set
		{
			_responseHeaderEncodingSelector = value ?? throw new ArgumentNullException("value");
		}
	}

	public IServiceProvider ApplicationServices { get; set; }

	public KestrelServerLimits Limits { get; } = new KestrelServerLimits();

	public KestrelConfigurationLoader? ConfigurationLoader { get; set; }

	private Action<ListenOptions> EndpointDefaults { get; set; } = (ListenOptions _) =>
	{
	};

	private Action<HttpsConnectionAdapterOptions> HttpsDefaults { get; set; } = (HttpsConnectionAdapterOptions _) =>
	{
	};

	internal X509Certificate2? DevelopmentCertificate { get; private set; }

	internal X509Certificate2? TestOverrideDefaultCertificate { get; set; }

	internal bool IsDevelopmentCertificateLoaded { get; set; }

	internal bool EnableWebTransportAndH3Datagrams
	{
		get
		{
			if (!_enableWebTransportAndH3Datagrams.HasValue)
			{
				_enableWebTransportAndH3Datagrams = AppContext.TryGetSwitch("Microsoft.AspNetCore.Server.Kestrel.Experimental.WebTransportAndH3Datagrams", out var isEnabled) & isEnabled;
			}
			return _enableWebTransportAndH3Datagrams.Value;
		}
		set
		{
			_enableWebTransportAndH3Datagrams = value;
		}
	}

	internal bool DisableHttp1LineFeedTerminators
	{
		get
		{
			if (!_disableHttp1LineFeedTerminators.HasValue)
			{
				_disableHttp1LineFeedTerminators = AppContext.TryGetSwitch("Microsoft.AspNetCore.Server.Kestrel.DisableHttp1LineFeedTerminators", out var isEnabled) & isEnabled;
			}
			return _disableHttp1LineFeedTerminators.Value;
		}
		set
		{
			_disableHttp1LineFeedTerminators = value;
		}
	}

	static KestrelServerOptions()
	{
		DefaultHeaderEncodingSelector = (string _) => (Encoding)null;
		AppContext.TryGetSwitch("Microsoft.AspNetCore.Server.Kestrel.FinOnError", out _finOnError);
		AppContext.TryGetSwitch("Microsoft.AspNetCore.Server.Kestrel.DisableCertificateFileWatching", out _disableCertificateFileWatching);
	}

	internal ListenOptions[] GetListenOptions()
	{
		int num = CodeBackedListenOptions.Count + ConfigurationBackedListenOptions.Count;
		if (num == 0)
		{
			return Array.Empty<ListenOptions>();
		}
		ListenOptions[] array = new ListenOptions[num];
		CodeBackedListenOptions.CopyTo(array);
		ConfigurationBackedListenOptions.CopyTo(array, CodeBackedListenOptions.Count);
		return array;
	}

	public void ConfigureEndpointDefaults(Action<ListenOptions> configureOptions)
	{
		EndpointDefaults = configureOptions ?? throw new ArgumentNullException("configureOptions");
	}

	internal void ApplyEndpointDefaults(ListenOptions listenOptions)
	{
		listenOptions.KestrelServerOptions = this;
		ConfigurationLoader?.ApplyEndpointDefaults(listenOptions);
		EndpointDefaults(listenOptions);
	}

	public void ConfigureHttpsDefaults(Action<HttpsConnectionAdapterOptions> configureOptions)
	{
		HttpsDefaults = configureOptions ?? throw new ArgumentNullException("configureOptions");
	}

	internal void ApplyHttpsDefaults(HttpsConnectionAdapterOptions httpsOptions)
	{
		ConfigurationLoader?.ApplyHttpsDefaults(httpsOptions);
		HttpsDefaults(httpsOptions);
	}

	internal void ApplyDefaultCertificate(HttpsConnectionAdapterOptions httpsOptions)
	{
		if (httpsOptions.HasServerCertificateOrSelector)
		{
			return;
		}
		X509Certificate2 testOverrideDefaultCertificate = TestOverrideDefaultCertificate;
		if (testOverrideDefaultCertificate != null)
		{
			httpsOptions.ServerCertificate = testOverrideDefaultCertificate;
			return;
		}
		X509Certificate2 x509Certificate = ConfigurationLoader?.DefaultCertificate;
		if (x509Certificate != null)
		{
			httpsOptions.ServerCertificate = x509Certificate;
			X509Certificate2Collection x509Certificate2Collection = ConfigurationLoader?.DefaultCertificateChain;
			if (x509Certificate2Collection != null)
			{
				httpsOptions.ServerCertificateChain = x509Certificate2Collection;
			}
			return;
		}
		if (!IsDevelopmentCertificateLoaded)
		{
			IsDevelopmentCertificateLoaded = true;
			ILogger<KestrelServer> requiredService = ApplicationServices.GetRequiredService<ILogger<KestrelServer>>();
			DevelopmentCertificate = GetDevelopmentCertificateFromStore(requiredService);
		}
		httpsOptions.ServerCertificate = DevelopmentCertificate;
	}

	internal void EnableHttpsConfiguration()
	{
		IHttpsConfigurationService requiredService = ApplicationServices.GetRequiredService<IHttpsConfigurationService>();
		if (!requiredService.IsInitialized)
		{
			IHostEnvironment requiredService2 = ApplicationServices.GetRequiredService<IHostEnvironment>();
			ILogger<KestrelServer> requiredService3 = ApplicationServices.GetRequiredService<ILogger<KestrelServer>>();
			ILogger<HttpsConnectionMiddleware> requiredService4 = ApplicationServices.GetRequiredService<ILogger<HttpsConnectionMiddleware>>();
			requiredService.Initialize(requiredService2, requiredService3, requiredService4);
		}
	}

	internal void Serialize(Utf8JsonWriter writer)
	{
		writer.WritePropertyName("AllowSynchronousIO");
		writer.WriteBooleanValue(AllowSynchronousIO);
		writer.WritePropertyName("AddServerHeader");
		writer.WriteBooleanValue(AddServerHeader);
		writer.WritePropertyName("AllowAlternateSchemes");
		writer.WriteBooleanValue(AllowAlternateSchemes);
		writer.WritePropertyName("AllowResponseHeaderCompression");
		writer.WriteBooleanValue(AllowResponseHeaderCompression);
		writer.WritePropertyName("IsDevelopmentCertificateLoaded");
		writer.WriteBooleanValue(IsDevelopmentCertificateLoaded);
		writer.WriteString("RequestHeaderEncodingSelector", (RequestHeaderEncodingSelector == DefaultHeaderEncodingSelector) ? "default" : "configured");
		writer.WriteString("ResponseHeaderEncodingSelector", (ResponseHeaderEncodingSelector == DefaultHeaderEncodingSelector) ? "default" : "configured");
		writer.WritePropertyName("Limits");
		writer.WriteStartObject();
		Limits.Serialize(writer);
		writer.WriteEndObject();
		writer.WritePropertyName("ListenOptions");
		writer.WriteStartArray();
		foreach (ListenOptions item in OptionsInUse)
		{
			writer.WriteStartObject();
			writer.WriteString("Address", item.GetDisplayName());
			writer.WritePropertyName("IsTls");
			writer.WriteBooleanValue(item.IsTls);
			writer.WriteString("Protocols", item.Protocols.ToString());
			writer.WriteEndObject();
		}
		writer.WriteEndArray();
	}

	private static X509Certificate2 GetDevelopmentCertificateFromStore(ILogger<KestrelServer> logger)
	{
		try
		{
			IList<X509Certificate2> list = CertificateManager.Instance.ListCertificates(StoreName.My, StoreLocation.CurrentUser, isValid: true, requireExportable: false);
			X509Certificate2 x509Certificate = ((list.Count > 0) ? list[0] : null);
			if (x509Certificate == null)
			{
				logger.UnableToLocateDevelopmentCertificate();
				return null;
			}
			CertificateManager.CheckCertificateStateResult checkCertificateStateResult = CertificateManager.Instance.CheckCertificateState(x509Certificate);
			if (!checkCertificateStateResult.Success)
			{
				logger.DeveloperCertificateFirstRun(checkCertificateStateResult.FailureMessage);
				return null;
			}
			switch (CertificateManager.Instance.GetTrustLevel(x509Certificate))
			{
			case CertificateManager.TrustLevel.Partial:
				logger.DeveloperCertificatePartiallyTrusted();
				break;
			case CertificateManager.TrustLevel.None:
				logger.DeveloperCertificateNotTrusted();
				break;
			}
			return x509Certificate;
		}
		catch
		{
			logger.UnableToLocateDevelopmentCertificate();
			return null;
		}
	}

	public KestrelConfigurationLoader Configure()
	{
		return Configure(new ConfigurationBuilder().Build());
	}

	public KestrelConfigurationLoader Configure(IConfiguration config)
	{
		return Configure(config, reloadOnChange: false);
	}

	public KestrelConfigurationLoader Configure(IConfiguration config, bool reloadOnChange)
	{
		if (ApplicationServices == null)
		{
			throw new InvalidOperationException("ApplicationServices must not be null. This is normally set automatically via IConfigureOptions.");
		}
		IHttpsConfigurationService requiredService = ApplicationServices.GetRequiredService<IHttpsConfigurationService>();
		CertificatePathWatcher certificatePathWatcher = ((reloadOnChange && !_disableCertificateFileWatching) ? new CertificatePathWatcher(ApplicationServices.GetRequiredService<IHostEnvironment>(), ApplicationServices.GetRequiredService<ILogger<CertificatePathWatcher>>()) : null);
		return ConfigurationLoader = new KestrelConfigurationLoader(this, config, requiredService, certificatePathWatcher, reloadOnChange);
	}

	public void Listen(IPAddress address, int port)
	{
		Listen(address, port, (ListenOptions _) =>
		{
		});
	}

	public void Listen(IPAddress address, int port, Action<ListenOptions> configure)
	{
		ArgumentNullException.ThrowIfNull(address, "address");
		Listen(new IPEndPoint(address, port), configure);
	}

	public void Listen(IPEndPoint endPoint)
	{
		Listen((EndPoint)endPoint);
	}

	public void Listen(EndPoint endPoint)
	{
		Listen(endPoint, (ListenOptions _) =>
		{
		});
	}

	public void Listen(IPEndPoint endPoint, Action<ListenOptions> configure)
	{
		Listen((EndPoint)endPoint, configure);
	}

	public void Listen(EndPoint endPoint, Action<ListenOptions> configure)
	{
		ArgumentNullException.ThrowIfNull(endPoint, "endPoint");
		ArgumentNullException.ThrowIfNull(configure, "configure");
		ListenOptions listenOptions = new ListenOptions(endPoint);
		ApplyEndpointDefaults(listenOptions);
		configure(listenOptions);
		CodeBackedListenOptions.Add(listenOptions);
	}

	public void ListenLocalhost(int port)
	{
		ListenLocalhost(port, (ListenOptions options) =>
		{
		});
	}

	public void ListenLocalhost(int port, Action<ListenOptions> configure)
	{
		ArgumentNullException.ThrowIfNull(configure, "configure");
		LocalhostListenOptions localhostListenOptions = new LocalhostListenOptions(port);
		ApplyEndpointDefaults(localhostListenOptions);
		configure(localhostListenOptions);
		CodeBackedListenOptions.Add(localhostListenOptions);
	}

	public void ListenAnyIP(int port)
	{
		ListenAnyIP(port, (ListenOptions options) =>
		{
		});
	}

	public void ListenAnyIP(int port, Action<ListenOptions> configure)
	{
		ArgumentNullException.ThrowIfNull(configure, "configure");
		AnyIPListenOptions anyIPListenOptions = new AnyIPListenOptions(port);
		ApplyEndpointDefaults(anyIPListenOptions);
		configure(anyIPListenOptions);
		CodeBackedListenOptions.Add(anyIPListenOptions);
	}

	public void ListenUnixSocket(string socketPath)
	{
		ListenUnixSocket(socketPath, (ListenOptions _) =>
		{
		});
	}

	public void ListenUnixSocket(string socketPath, Action<ListenOptions> configure)
	{
		ArgumentNullException.ThrowIfNull(socketPath, "socketPath");
		if (!Path.IsPathRooted(socketPath))
		{
			throw new ArgumentException(CoreStrings.UnixSocketPathMustBeAbsolute, "socketPath");
		}
		ArgumentNullException.ThrowIfNull(configure, "configure");
		ListenOptions listenOptions = new ListenOptions(socketPath);
		ApplyEndpointDefaults(listenOptions);
		configure(listenOptions);
		CodeBackedListenOptions.Add(listenOptions);
	}

	public void ListenHandle(ulong handle)
	{
		ListenHandle(handle, (ListenOptions _) =>
		{
		});
	}

	public void ListenHandle(ulong handle, Action<ListenOptions> configure)
	{
		ArgumentNullException.ThrowIfNull(configure, "configure");
		ListenOptions listenOptions = new ListenOptions(handle);
		ApplyEndpointDefaults(listenOptions);
		configure(listenOptions);
		CodeBackedListenOptions.Add(listenOptions);
	}

	public void ListenNamedPipe(string pipeName)
	{
		ListenNamedPipe(pipeName, (ListenOptions _) =>
		{
		});
	}

	public void ListenNamedPipe(string pipeName, Action<ListenOptions> configure)
	{
		ArgumentNullException.ThrowIfNull(pipeName, "pipeName");
		ArgumentNullException.ThrowIfNull(configure, "configure");
		ListenOptions listenOptions = new ListenOptions(new NamedPipeEndPoint(pipeName));
		ApplyEndpointDefaults(listenOptions);
		configure(listenOptions);
		CodeBackedListenOptions.Add(listenOptions);
	}
}
