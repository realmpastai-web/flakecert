# Ideal customer profile

Draft. Not sent. No buyer has been contacted.

The draft buyer is a US or EU team that already runs nginx or HAProxy in front of a .NET Kestrel origin, and that has both a platform engineer who can change that front and a security engineer who accepts residual risk on it. The profile is the target named for this pilot. It is not a measured headcount.

## What was fetched on 2026-10-27

### nginx in front of Kestrel

Microsoft Learn, "Host ASP.NET Core on Linux with Nginx" (ASP.NET Core 10 view):

https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/linux-nginx?view=aspnetcore-10.0

The page says: "A reverse proxy is a common setup for serving dynamic web apps. A reverse proxy terminates the HTTP request and forwards it to the ASP.NET Core app." It then says: "For the purposes of this guide, a single instance of Nginx is used." The configuration on that page uses `proxy_pass` and states that Nginx forwards matching requests to Kestrel.

Microsoft Learn, "When to use a reverse proxy with the ASP.NET Core Kestrel web server" (ASP.NET Core 10 view):

https://learn.microsoft.com/en-us/aspnet/core/fundamentals/servers/kestrel/when-to-use-a-reverse-proxy?view=aspnetcore-10.0

The page lists example reverse proxies: Internet Information Services (IIS), Nginx, Apache, and YARP. HAProxy is not in that list.

Microsoft Learn, "Configure ASP.NET Core to work with proxy servers and load balancers" (ASP.NET Core 10 view):

https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/proxy-load-balancer?view=aspnetcore-10.0

The page says the recommended configuration hosts the app with the ASP.NET Core Module for IIS, Nginx, or Apache. HAProxy is not named in that sentence.

### HAProxy in front of ASP.NET Core

Public architecture post, Dan Horrocks-Burgess, 8 July 2019, "ASP.NET Core Reverse Proxy Support With HAProxy":

https://www.danhb.dev/blog/2019/07/asp-net-core-reverse-proxy-support-with-haproxy/

The post says: "A Microsoft Azure hosted Kubernetes cluster (AKS) is used to host the web app using HAProxy as an Ingress Controller." The app in that post is ASP.NET Core 2.2. This is one public write-up. It is not a vendor hosting guide, and it is not the pinned HAProxy 3.4.7 / Kestrel 10.0.12 pair scored in `desync-oracle/`.

Public issue on `dotnet/aspnetcore`, title "Lack of proxy-protocol support prevents use of Kestrel with HAproxy in TCP mode":

https://github.com/dotnet/aspnetcore/issues/28526

That title is evidence that HAProxy and Kestrel are discussed together. The thread is about TCP mode. The scored HAProxy profile in this pilot is `mode http`. TCP mode is outside the scored rating (`desync-oracle/README.md`, H-ARCH).

## NEEDS-CITE

- Job posts that hire for nginx or HAProxy in front of Kestrel in the US or the EU. None were fetched. Do not treat the draft geography as a count of openings.
- A prevalence figure for this stack. None was fetched.
- A Microsoft Learn page that names HAProxy as a supported Kestrel reverse proxy. The three Learn pages above do not. A later draft that wants that sentence needs its own fetch.
- A current (2026) architecture post that pairs HAProxy 3.4 with Kestrel 10. The 2019 post above is the fetched HAProxy write-up.

## Draft fit

The pilot fits when the deployment is one of the two published profiles: nginx 1.28.3 `proxy_pass`, or HAProxy 3.4.7 `mode http`, in front of Kestrel, and the buyer can run the lab config gate in `SCOPE.md` on a non-production copy.

A deployment on nginx `stream`, HAProxy `mode tcp`, a front this oracle did not read, or Kestrel published with no HTTP front, is outside the sealed rating. `SCOPE.md` says what the two weeks include.
