set -eux;

export PYTHON_VERSION=3.12.2

# Install buildpack-deps packages
apt-get install -y \
    autoconf \
    automake \
    bzip2 \
    default-libmysqlclient-dev \
    dpkg-dev \
    file \
    g++ \
    gcc \
    imagemagick \
    libbz2-dev \
    libc6-dev \
    libcurl4-openssl-dev \
    libdb-dev \
    libevent-dev \
    libffi-dev \
    libgdbm-dev \
    libglib2.0-dev \
    libgmp-dev \
    libjpeg-dev \
    libkrb5-dev \
    liblzma-dev \
    libmagickcore-dev \
    libmagickwand-dev \
    libmaxminddb-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libpng-dev \
    libpq-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    libtool \
    libwebp-dev \
    libxml2-dev \
    libxslt1-dev \
    libyaml-dev \
    make \
    patch \
    unzip \
    xz-utils \
    zlib1g-dev \
    tk-dev \
    uuid-dev

# Get python source code
wget -O python.tar.xz "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz"

mkdir -p /usr/src/python

tar --extract --directory /usr/src/python --strip-components=1 --file python.tar.xz

rm -f python.tar.xz

# Compile python from source
cd /usr/src/python

./configure --build="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)" --enable-loadable-sqlite-extensions --enable-optimizations --enable-option-checking=fatal --enable-shared --with-lto --with-system-expat --without-ensurepip

make -j "$(nproc)" "EXTRA_CFLAGS=$(dpkg-buildflags --get CFLAGS)" "LDFLAGS=$(dpkg-buildflags --get LDFLAGS)"

# https://github.com/docker-library/python/issues/784
# prevent accidental usage of a system installed libpython of the same version
rm -f python

make -j "$(nproc)" "EXTRA_CFLAGS=$(dpkg-buildflags --get CFLAGS)" "LDFLAGS=$(dpkg-buildflags --get LDFLAGS),-rpath='\$\$ORIGIN/../lib'" python

make install

# enable GDB to load debugging data: https://github.com/docker-library/python/pull/701
bin="$(readlink -ve /usr/local/bin/python3)"
dir="$(dirname "$bin")"
mkdir -p "/usr/share/gdb/auto-load/$dir"

cp -vL Tools/gdb/libpython.py "/usr/share/gdb/auto-load/$bin-gdb.py"

cd /

rm -rf /usr/src/python

find /usr/local -depth \
    \( \
        \( -type d -a \( -name test -o -name tests -o -name idle_test \) \) \
        -o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' -o -name 'libpython*.a' \) \) \
    \) -exec rm -rf '{}' +

ldconfig

python3 --version

# make some useful symlinks that are expected to exist ("/usr/local/bin/python" and friends)
for src in idle3 pydoc3 python3 python3-config; do \
    dst="$(echo "$src" | tr -d 3)"; \
    [ -s "/usr/local/bin/$src" ]; \
    [ ! -e "/usr/local/bin/$dst" ]; \
    ln -svT "$src" "/usr/local/bin/$dst"; \
done

# check python version
python --version

# install latest pip version
wget -O get-pip.py https://github.com/pypa/get-pip/raw/dbf0c85f76fb6e1ab42aa672ffca6f0a675d9ee4/public/get-pip.py

python get-pip.py --disable-pip-version-check --no-cache-dir --no-compile "pip"

rm -f get-pip.py

# check pip version
pip --version
