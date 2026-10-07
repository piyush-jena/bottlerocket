%global _cross_first_party 1

Name: %{_cross_os}kexec-probe
Version: 0.1.0
Release: 1%{?dist}
Summary: Private Symphony issue 17 kexec calibration probe
License: MIT
URL: https://github.com/bottlerocket-os/bottlerocket
Source0: kexec-probe.c
Source1: LICENSE-MIT
BuildRequires: %{_cross_os}glibc-devel

%description
Private validation helper for nonloading syscall probes and process context.
This package is only included in issue 17 calibration images.

%prep
%setup -q -c -T
cp %{SOURCE0} %{SOURCE1} .

%build
%{_cross_target}-gcc %{_cross_cflags} %{_cross_ldflags} \
  -std=c11 -Wall -Wextra -Werror -o kexec-probe kexec-probe.c
%{_cross_target}-gcc --version > compiler.txt

%install
install -D -m0755 kexec-probe %{buildroot}%{_cross_bindir}/kexec-probe
install -D -m0644 kexec-probe.c %{buildroot}%{_cross_datadir}/kexec-probe/kexec-probe.c
install -D -m0644 compiler.txt %{buildroot}%{_cross_datadir}/kexec-probe/compiler.txt

%files
%license LICENSE-MIT
%{_cross_bindir}/kexec-probe
%{_cross_datadir}/kexec-probe/

