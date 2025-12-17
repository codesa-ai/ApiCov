* Make sure to have automake and libtool installed
`sudo apt-get install automake libtool`
* Make sure to have ogg installed and pkgconfig 
`sudo apt-get install -y libogg-dev pkg-config`
* Run `./autogen.sh` followed by `./configure CFLAGS="--coverage -O0"`
* Run `make && make check`
