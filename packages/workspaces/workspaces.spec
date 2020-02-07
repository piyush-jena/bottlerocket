%global migration_dir %{_cross_factorydir}%{_cross_sharedstatedir}/thar/datastore/migrations
%global _cross_first_party 1
%undefine _debugsource_packages

Name: %{_cross_os}workspaces
Version: 0.0
Release: 0%{?dist}
Summary: Thar's first-party code
License: LicenseRef-Pending

# sources < 100: misc
Source1: data-store-version
Source2: api-sysusers.conf
# Taken from https://github.com/awslabs/amazon-eks-ami/blob/master/files/eni-max-pods.txt
Source3: eni-max-pods

Source4: root.json
Source5: updog-toml

# 1xx sources: systemd units
Source100: apiserver.service
Source101: moondog.service
Source102: sundog.service
Source103: storewolf.service
Source105: settings-applier.service
Source106: migrator.service
Source107: host-containers@.service
Source108: updog.timer
Source109: updog.service
Source110: mark-successful-boot.service

# 2xx sources: tmpfilesd configs
Source200: migration-tmpfiles.conf
Source201: host-containers-tmpfiles.conf

BuildRequires: %{_cross_os}glibc-devel

%description
%{summary}.

%package -n %{_cross_os}apiserver
Summary: Thar API server
%description -n %{_cross_os}apiserver
%{summary}.

%package -n %{_cross_os}apiclient
Summary: Thar API client
%description -n %{_cross_os}apiclient
%{summary}.

%package -n %{_cross_os}moondog
Summary: Thar userdata configuration system
Requires: %{_cross_os}apiserver = %{version}-%{release}
%description -n %{_cross_os}moondog
%{summary}.

%package -n %{_cross_os}netdog
Summary: Thar network configuration helper
Requires: %{_cross_os}apiserver = %{version}-%{release}
%description -n %{_cross_os}netdog
%{summary}.

%package -n %{_cross_os}sundog
Summary: Updates settings dynamically based on user-specified generators
Requires: %{_cross_os}apiserver = %{version}-%{release}
Requires: %{_cross_os}schnauzer = %{version}-%{release}
Requires: %{_cross_os}pluto = %{version}-%{release}
Requires: %{_cross_os}bork = %{version}-%{release}
%description -n %{_cross_os}sundog
%{summary}.

%package -n %{_cross_os}bork
Summary: Dynamic setting generator for updog
%description -n %{_cross_os}bork
%{summary}.

%package -n %{_cross_os}schnauzer
Summary: Setting generator for templated settings values.
%description -n %{_cross_os}schnauzer
%{summary}.

%package -n %{_cross_os}pluto
Summary: Dynamic setting generator for kubernetes
%description -n %{_cross_os}pluto
%{summary}.

%package -n %{_cross_os}thar-be-settings
Summary: Applies changed settings to a Thar system
Requires: %{_cross_os}apiserver = %{version}-%{release}
%description -n %{_cross_os}thar-be-settings
%{summary}.

%package -n %{_cross_os}servicedog
Summary: Manipulates systemd units based on setting changes
Requires: %{_cross_os}apiserver = %{version}-%{release}
%description -n %{_cross_os}servicedog
%{summary}.

%package -n %{_cross_os}host-containers
Summary: Manages system- and user-defined host containers
Requires: %{_cross_os}apiserver = %{version}-%{release}
Requires: %{_cross_os}host-ctr
%description -n %{_cross_os}host-containers
%{summary}.

%package -n %{_cross_os}storewolf
Summary: Data store creator
Requires: %{_cross_os}apiserver = %{version}-%{release}
%description -n %{_cross_os}storewolf
%{summary}.

%package -n %{_cross_os}migration
Summary: Tools to migrate version formats
Requires: %{_cross_os}apiserver = %{version}-%{release}
%description -n %{_cross_os}migration

%package -n %{_cross_os}settings-committer
Summary: Commits settings from user data, defaults, and generators at boot
%description -n %{_cross_os}settings-committer
%{summary}.

%package -n %{_cross_os}growpart
Summary: Tool to grow partitions
%description -n %{_cross_os}growpart
%{summary}.

%package -n %{_cross_os}signpost
Summary: Thar GPT priority querier/switcher
%description -n %{_cross_os}signpost
%{summary}.

%package -n %{_cross_os}updog
Summary: Thar updater CLI
%description -n %{_cross_os}updog
not much what's up with you

%package -n %{_cross_os}preinit
Summary: Thar pre-init system setup
%description -n %{_cross_os}preinit
%{summary}.

%package -n %{_cross_os}migrations
Summary: Thar data store migrations
%description -n %{_cross_os}migrations
%{summary}.

%prep
%setup -T -c
%cargo_prep

%build
mkdir bin
%cargo_build --manifest-path %{_builddir}/workspaces/Cargo.toml \
    -p apiserver \
    -p moondog \
    -p netdog \
    -p sundog \
    -p schnauzer \
    -p pluto \
    -p bork \
    -p thar-be-settings \
    -p servicedog \
    -p host-containers \
    -p storewolf \
    -p settings-committer \
    -p migrator \
    -p signpost \
    -p updog \
    -p growpart \
    -p laika \
    %{nil}

%cargo_build_static --manifest-path %{_builddir}/workspaces/Cargo.toml \
    -p apiclient \
    %{nil}

# Build the migrations
for crate in $(find %{_builddir}/workspaces/api/migration/migrations -name 'Cargo.toml'); do
    %cargo_build_static --manifest-path "${crate}"
done

%install
install -d %{buildroot}%{_cross_bindir}
for p in \
  apiserver \
  moondog netdog sundog schnauzer pluto bork \
  thar-be-settings servicedog host-containers \
  storewolf settings-committer \
  migrator \
  signpost updog ;
do
  install -p -m 0755 ${HOME}/.cache/%{__cargo_target}/release/${p} %{buildroot}%{_cross_bindir}
done

for p in apiclient ; do
  install -p -m 0755 ${HOME}/.cache/%{__cargo_target_static}/release/${p} %{buildroot}%{_cross_bindir}
done

install -d %{buildroot}%{_cross_sbindir}
for p in growpart preinit ; do
  install -p -m 0755 ${HOME}/.cache/%{__cargo_target}/release/${p} %{buildroot}%{_cross_sbindir}
done

install -d %{buildroot}%{_cross_datadir}/migrations
for version_path in %{_builddir}/workspaces/api/migration/migrations/*; do
  for migration_path in "${version_path}"/*; do
    version="${version_path##*/}"
    crate_name="${migration_path##*/}"
    migration_binary_name="migrate_${version}_${crate_name#migrate-}"
    built_path="${HOME}/.cache/%{__cargo_target_static}/release/${crate_name}"
    target_path="%{buildroot}%{_cross_datadir}/migrations/${migration_binary_name}"

    install -m 0555 "${built_path}" "${target_path}"
  done
done

install -d %{buildroot}%{migration_dir}

install -d %{buildroot}%{_cross_datadir}/thar
install -p -m 0644 %{S:1} %{buildroot}%{_cross_datadir}/thar

install -d %{buildroot}%{_cross_sysusersdir}
install -p -m 0644 %{S:2} %{buildroot}%{_cross_sysusersdir}/api.conf

install -d %{buildroot}%{_cross_datadir}/eks
install -p -m 0644 %{S:3} %{buildroot}%{_cross_datadir}/eks

install -d %{buildroot}%{_cross_datadir}/updog
install -p -m 0644 %{S:4} %{buildroot}%{_cross_datadir}/updog

install -d %{buildroot}%{_cross_templatedir}
install -p -m 0644 %{S:5} %{buildroot}%{_cross_templatedir}

install -d %{buildroot}%{_cross_unitdir}
install -p -m 0644 \
  %{S:100} %{S:101} %{S:102} %{S:103} %{S:105} \
  %{S:106} %{S:107} %{S:108} %{S:109} %{S:110} \
  %{buildroot}%{_cross_unitdir}

install -d %{buildroot}%{_cross_tmpfilesdir}
install -p -m 0644 %{S:200} %{buildroot}%{_cross_tmpfilesdir}/migration.conf
install -p -m 0644 %{S:201} %{buildroot}%{_cross_tmpfilesdir}/host-containers.conf

%files -n %{_cross_os}apiserver
%{_cross_bindir}/apiserver
%{_cross_unitdir}/apiserver.service
%{_cross_unitdir}/migrator.service
%{_cross_datadir}/thar/data-store-version
%{_cross_sysusersdir}/api.conf

%files -n %{_cross_os}apiclient
%{_cross_bindir}/apiclient

%files -n %{_cross_os}moondog
%{_cross_bindir}/moondog
%{_cross_unitdir}/moondog.service

%files -n %{_cross_os}netdog
%{_cross_bindir}/netdog

%files -n %{_cross_os}sundog
%{_cross_bindir}/sundog
%{_cross_unitdir}/sundog.service

%files -n %{_cross_os}schnauzer
%{_cross_bindir}/schnauzer

%files -n %{_cross_os}pluto
%{_cross_bindir}/pluto
%dir %{_cross_datadir}/eks
%{_cross_datadir}/eks/eni-max-pods

%files -n %{_cross_os}bork
%{_cross_bindir}/bork

%files -n %{_cross_os}thar-be-settings
%{_cross_bindir}/thar-be-settings
%{_cross_unitdir}/settings-applier.service

%files -n %{_cross_os}servicedog
%{_cross_bindir}/servicedog

%files -n %{_cross_os}host-containers
%{_cross_bindir}/host-containers
%{_cross_unitdir}/host-containers@.service
%{_cross_tmpfilesdir}/host-containers.conf

%files -n %{_cross_os}storewolf
%{_cross_bindir}/storewolf
%{_cross_unitdir}/storewolf.service

%files -n %{_cross_os}migration
%{_cross_bindir}/migrator
%{migration_dir}
%{_cross_tmpfilesdir}/migration.conf

%files -n %{_cross_os}migrations
%dir %{_cross_datadir}/migrations
%{_cross_datadir}/migrations

%files -n %{_cross_os}settings-committer
%{_cross_bindir}/settings-committer

%files -n %{_cross_os}growpart
%{_cross_sbindir}/growpart

%files -n %{_cross_os}signpost
%{_cross_bindir}/signpost
%{_cross_unitdir}/mark-successful-boot.service

%files -n %{_cross_os}updog
%{_cross_bindir}/updog
%{_cross_datadir}/updog
%dir %{_cross_templatedir}
%{_cross_templatedir}/updog-toml
%{_cross_unitdir}/updog.timer
%{_cross_unitdir}/updog.service

%files -n %{_cross_os}preinit
%{_cross_sbindir}/preinit

%changelog
