# Local RHEL 10 dependency package, built from upstream commit
# d37c16111dbe38ea29194f20ac9de03cff8dfc1c (v4.20260303.1).
%global debug_package %{nil}

Name:           xdotool
Version:        4.20260303.1
Release:        1%{?dist}
Summary:        X11 input and window automation for the Jarvis Linux port
License:        BSD-3-Clause
URL:            https://github.com/jordansissel/xdotool
Source0:        xdotool-%{version}.tar.gz
ExclusiveArch:  x86_64 aarch64
BuildRequires:  gcc make pkgconf-pkg-config
BuildRequires:  libX11-devel libXtst-devel libXinerama-devel libxkbcommon-devel
BuildRequires:  perl(Pod::Man)

%description
Native X11 automation tool and its runtime library. This local dependency
package fills the missing xdotool provider on the tested RHEL 10 baseline.
It is not an official distribution repository package.

%prep
%setup -q
# The system library directory is already searched by the dynamic loader.
sed -i '/^xdotool: LDFLAGS+=-Xlinker$/d; /^xdotool: LDFLAGS+=-rpath $(INSTALLLIB)$/d' Makefile

%build
%set_build_flags
%make_build PREFIX=%{_prefix} INSTALLLIB=%{_libdir} INSTALLMAN=%{_mandir}

%install
%{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} INSTALLLIB=%{_libdir} \
    INSTALLMAN=%{_mandir} installlib installprog installman
rm -f %{buildroot}%{_libdir}/libxdo.so

%check
LD_LIBRARY_PATH=%{buildroot}%{_libdir} %{buildroot}%{_bindir}/xdotool version

%files
%{_bindir}/xdotool
%{_libdir}/libxdo.so.4
%{_mandir}/man1/xdotool.1*
%license COPYRIGHT

%changelog
* Fri Oct 16 2026 Jarvis contributors - 4.20260303.1-1
- Build the pinned X11 tool natively for the RHEL 10 port.
