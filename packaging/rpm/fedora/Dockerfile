FROM registry.fedoraproject.org/fedora:44
RUN dnf install -y --setopt=install_weak_deps=False \
    rpm-build rust cargo gcc gcc-c++ make pkgconf-pkg-config \
    gtk3-devel webkit2gtk4.1-devel python3 python3-pip python3-rpm-macros \
    nodejs npm git ca-certificates && dnf clean all
WORKDIR /build/jarvis
COPY . .
# Docker excludes .git; the explicit context is already filtered by .dockerignore.
RUN mkdir -p /root/rpmbuild/SOURCES /root/rpmbuild/SPECS && \
    tar --exclude='./.git' --exclude='./.superpowers' --exclude='./dist' \
        --transform='s,^\.,jarvis-0.1.0,' -czf /root/rpmbuild/SOURCES/jarvis-0.1.0.tar.gz . && \
    cp packaging/rpm/fedora/jarvis-assistant.spec /root/rpmbuild/SPECS/ && \
    rpmbuild -ba /root/rpmbuild/SPECS/jarvis-assistant.spec
CMD ["sh", "-c", "cp /root/rpmbuild/RPMS/*/*.rpm /root/rpmbuild/SRPMS/*.rpm /out/"]
