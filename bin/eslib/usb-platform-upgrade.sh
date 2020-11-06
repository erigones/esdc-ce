#!/bin/bash

# https://github.com/calmh/smartos-platform-upgrade
# Copyright (c) 2012-2016 Jakob Borg & Contributors
# Distributed under the MIT License
#
# Modified to work on Danube cloud by Paolo Marcheschi
#
cert_file=$(mktemp)
function cleanup {
        rm "$cert_file"
}
trap cleanup EXIT
cat >"$cert_file" <<EOF
-----BEGIN CERTIFICATE-----
MIIFdzCCBF+gAwIBAgISBPzllbVY44lRFupmsOVpFqyaMA0GCSqGSIb3DQEBCwUA
MEoxCzAJBgNVBAYTAlVTMRYwFAYDVQQKEw1MZXQncyBFbmNyeXB0MSMwIQYDVQQD
ExpMZXQncyBFbmNyeXB0IEF1dGhvcml0eSBYMzAeFw0yMDEwMDIwNjU5MDNaFw0y
MDEyMzEwNjU5MDNaMB4xHDAaBgNVBAMTE3BrZ3NyYy5lcmlnb25lcy5jb20wggEi
MA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDaEJZXHh35jsqFIBK+pmsFsY5Q
+wE1bocePFV9IHuToPYLEEEd1kpfgGOFie6KMBXZyHDfzX29AIitBT4Kht9QFeWI
WJob26RmF4v+pEfKjqayRmdqE08PMUmJVL7VmjpfQ0qMRYFsPj9fzPpAGOd/4AlP
kyzmQxJiGicW0glVrWJig286gIwjM5D9CEGx8myajRTy2to22CdUhkY+mn4MukVB
/hiRoL3D2eB/BOwKL4JGSE+uK6S4VG8chRfMjHQisaDnLItZ7yE4wm25FYCOCQqc
uGtjyqku7WvQcN5Mh7VIUgp4THNjv7BypJaTElKhTOjrSPldjwWepSGN/pKBAgMB
AAGjggKBMIICfTAOBgNVHQ8BAf8EBAMCBaAwHQYDVR0lBBYwFAYIKwYBBQUHAwEG
CCsGAQUFBwMCMAwGA1UdEwEB/wQCMAAwHQYDVR0OBBYEFO7RvZ307AeDih2y8CRo
j4J4ciRsMB8GA1UdIwQYMBaAFKhKamMEfd265tE5t6ZFZe/zqOyhMG8GCCsGAQUF
BwEBBGMwYTAuBggrBgEFBQcwAYYiaHR0cDovL29jc3AuaW50LXgzLmxldHNlbmNy
eXB0Lm9yZzAvBggrBgEFBQcwAoYjaHR0cDovL2NlcnQuaW50LXgzLmxldHNlbmNy
eXB0Lm9yZy8wNQYDVR0RBC4wLIIVZG93bmxvYWQuZGFudWJlLmNsb3VkghNwa2dz
cmMuZXJpZ29uZXMuY29tMEwGA1UdIARFMEMwCAYGZ4EMAQIBMDcGCysGAQQBgt8T
AQEBMCgwJgYIKwYBBQUHAgEWGmh0dHA6Ly9jcHMubGV0c2VuY3J5cHQub3JnMIIB
BgYKKwYBBAHWeQIEAgSB9wSB9ADyAHcAXqdz+d9WwOe1Nkh90EngMnqRmgyEoRIS
hBh1loFxRVgAAAF06FJSDgAABAMASDBGAiEAigIorLmlispsd3E4ekIFSXn5dSeH
HxxEQHYsws1wQhcCIQD9YfGPmAcK03mvXtFaIIqiIIc4J9/vCW6Fazejiu50gAB3
AAe3XBvlfWj/8bDGHSMVx7rmV3xXlLdq7rxhOhpp06IcAAABdOhSUigAAAQDAEgw
RgIhAP99vJgcCngAoksF5HqzgUAEXGcO0cluZVPrUgq+hN5qAiEA5qay3yHredM2
EUDTdFvs8Fp/f/q+0ARmoajK2YAoZVYwDQYJKoZIhvcNAQELBQADggEBAA5Z85fi
FekX1hWMHHyM9fGmwCNN+RPvwAIrZHtPnwb3RaINMraGotEXP1Rt1Mlqx6oWVvwf
GhvPyvJsrxhLQ3lLmP4qTyIzhPHbhYLwh/bodFO/gP9wFk06sd1qPjdSXfoP/qiE
0cSDPjxDHt6sKahMNAbbNkZceJLnT+kxSCPt9YCYw0+g1PK1ay3uoeU+Q+/TP6D2
xCk5yn2ostDA73SSvwx8p9uMhwvhvhnlfY5az29fdVeK019Djlzip46i9D/DbNHY
SwhTipsh+OMaqq93YxBZEbegLR0g0YYXoAO//n/7gjMA0e8RJs/uoAMvGpSwxBXu
+S+JEHNyRRKGD/E=
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIEkjCCA3qgAwIBAgIQCgFBQgAAAVOFc2oLheynCDANBgkqhkiG9w0BAQsFADA/
MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNVBAMT
DkRTVCBSb290IENBIFgzMB4XDTE2MDMxNzE2NDA0NloXDTIxMDMxNzE2NDA0Nlow
SjELMAkGA1UEBhMCVVMxFjAUBgNVBAoTDUxldCdzIEVuY3J5cHQxIzAhBgNVBAMT
GkxldCdzIEVuY3J5cHQgQXV0aG9yaXR5IFgzMIIBIjANBgkqhkiG9w0BAQEFAAOC
AQ8AMIIBCgKCAQEAnNMM8FrlLke3cl03g7NoYzDq1zUmGSXhvb418XCSL7e4S0EF
q6meNQhY7LEqxGiHC6PjdeTm86dicbp5gWAf15Gan/PQeGdxyGkOlZHP/uaZ6WA8
SMx+yk13EiSdRxta67nsHjcAHJyse6cF6s5K671B5TaYucv9bTyWaN8jKkKQDIZ0
Z8h/pZq4UmEUEz9l6YKHy9v6Dlb2honzhT+Xhq+w3Brvaw2VFn3EK6BlspkENnWA
a6xK8xuQSXgvopZPKiAlKQTGdMDQMc2PMTiVFrqoM7hD8bEfwzB/onkxEz0tNvjj
/PIzark5McWvxI0NHWQWM6r6hCm21AvA2H3DkwIDAQABo4IBfTCCAXkwEgYDVR0T
AQH/BAgwBgEB/wIBADAOBgNVHQ8BAf8EBAMCAYYwfwYIKwYBBQUHAQEEczBxMDIG
CCsGAQUFBzABhiZodHRwOi8vaXNyZy50cnVzdGlkLm9jc3AuaWRlbnRydXN0LmNv
bTA7BggrBgEFBQcwAoYvaHR0cDovL2FwcHMuaWRlbnRydXN0LmNvbS9yb290cy9k
c3Ryb290Y2F4My5wN2MwHwYDVR0jBBgwFoAUxKexpHsscfrb4UuQdf/EFWCFiRAw
VAYDVR0gBE0wSzAIBgZngQwBAgEwPwYLKwYBBAGC3xMBAQEwMDAuBggrBgEFBQcC
ARYiaHR0cDovL2Nwcy5yb290LXgxLmxldHNlbmNyeXB0Lm9yZzA8BgNVHR8ENTAz
MDGgL6AthitodHRwOi8vY3JsLmlkZW50cnVzdC5jb20vRFNUUk9PVENBWDNDUkwu
Y3JsMB0GA1UdDgQWBBSoSmpjBH3duubRObemRWXv86jsoTANBgkqhkiG9w0BAQsF
AAOCAQEA3TPXEfNjWDjdGBX7CVW+dla5cEilaUcne8IkCJLxWh9KEik3JHRRHGJo
uM2VcGfl96S8TihRzZvoroed6ti6WqEBmtzw3Wodatg+VyOeph4EYpr/1wXKtx8/
wApIvJSwtmVi4MFU5aMqrSDE6ea73Mj2tcMyo5jMd6jmeWUHK8so/joWUoHOUgwu
X4Po1QYz+3dszkDqMp4fklxBwXRsW10KXzPMTZ+sOPAveyxindmjkW8lGy+QsRlG
PfZ+G6Z6h7mjem0Y+iWlkYcV4PIWL1iwBi8saCbGS5jN2p8M+X+Q7UNKEkROb3N6
KOqkqm57TH2H3eDJAkSnh6/DNFu0Qg==
-----END CERTIFICATE-----
EOF

function _curl {
        curl -s -k --cacert "$cert_file" $@
}
function usage() {
    cat <<- "USAGE"
$ platform-upgrade [-u URL -s MD5SUM_URL] [-f]

OPTIONS:
  -u URL        : Remote/local url of platform-version.tgz file
  -s MD5SUM_URL : Remote/local url of md5 checksum file
  -f            : Force installation if version is already present

EXAMPLE:
  # use remote platform file
  platform-upgrade -u https://download.danube.cloud/esdc/factory/platform/platform-20201105T132431Z.tgz
  # Use local platform and checksum file
  platform-upgrade -u file:///tmp/platform-20180510T153535Z.tgz -s file:///tmp/md5sum.txt
  # DC upgrade
  ./platform-upgrade -u file:///zones/TEMP/platform-20201105T132431Z.tgz -s file:///zones/TEMP/md5.txt
USAGE
}

force="false"
while getopts :fu:s: option; do
    case "$option" in
        u)
            platform_url="$OPTARG"
            ;;
        s)
            md5sums_url="$OPTARG"
            ;;
        f)
            force="true"
            ;;
        \?)
            usage
            exit -1
            ;;
    esac
done
shift $((OPTIND-1))


if [[ ! -n $platform_url ]]; then
	usage
	exit -1
else
    header="$(expr "$platform_url" : '.*platform-\([0-9]\{8\}\)-.*')"
    version="$(expr "$platform_url" : '.*\([0-9]\{8\}T[0-9]\{6\}Z\).*')"
fi

platform_file="platform-$version.tgz"
platform_dir="platform-$version"

IFS=_ read brand kernel < <(uname -v)
echo "Brand="  $brand
echo "Actual kernel= " $kernel
echo "New Version= " $version
if [[ $kernel == $version ]]; then
    echo "Already on latest version ($kernel)."
    $force || exit -1
fi

tmp=$(mktemp -d -p /tmp -t)
cd "$tmp" || exit -1

echo -n "Downloading $platform_file..."
if ! _curl -o "$platform_file" "$platform_url" ; then
        echo " failed"
        exit -1
else
        echo " OK"
fi
#echo "md5sum= |"$md5sums_url"|"
if [[ -n "$md5sums_url" ]]; then
  echo -n "Verifying checksum..."
  _curl "$md5sums_url" \
        | grep "$platform_file" \
        | awk '{print $1}' > expected.md5
  openssl md5 "$platform_file" | awk '{print $2}' > actual.md5
  if ! cmp -s actual.md5 expected.md5 ; then
        echo " failed"
        exit -1
  else
        echo " OK"
fi
fi
echo -n "Extracting latest platform..."
if ! gtar zxf "$platform_file" ; then
        echo " failed"
        exit -1
else
        echo " OK"
fi

echo -n "Marking release version..."
if ! echo $version > $platform_dir/VERSION ; then
        echo " failed"
        exit -1
else
        echo " OK"
fi

echo -n "Checking current boot device..."
if [[ -z $1 ]] ; then
        removables=($(diskinfo -cH | \
                      awk 'BEGIN { FS="\t" } $7~/\?\?R./ { print $2 }'))
        echo -n " detected ${removables[@]}"
        if [[ ${#removables[@]} -eq 0 ]]; then
                echo
                echo "Error: Unable to detect removable device."
                diskinfo
                echo "Specify correct device on the command line."
                exit -1
        elif [[ ${#removables[@]} -gt 1 ]]; then
                echo
                echo "Error: more than one removable device detected."
                diskinfo -cH | awk 'BEGIN { FS="\t" } $7~/\?\?R./ { print }'
                echo "Specify correct device on the command line."
                exit -1
        fi
        # Look for a GPT/EFI VTOC; if there isn't one, then this is almost
        # certainly an MBR-partitioned device. If it's a GPT label, then we
        # want the slice that's of type 2 (ROOT).
        if [[ -e "/dev/dsk/${removables[0]}" ]]; then
                partition=$(/usr/sbin/prtvtoc -h "/dev/dsk/${removables[0]}" | \
                            awk ' $2 == 2 { print $1 }')
                if [[ $? -eq 0 && -n "$partition" ]]; then
                        echo -n ", GPT label"
                        usb="/dev/dsk/${removables[0]}s${partition}"
                fi
        fi
        if [[ -z "$usb" ]]; then
                echo -n ", MBR label"
                usb="/dev/dsk/${removables[0]}p1"
        fi
else
        usb="$1"
        echo -n " using $usb"
fi
echo "usb path= " $usb
umount "$usb" 2>/dev/null
mkdir usb
if ! mount -F pcfs -o foldcase "$usb" "$tmp/usb" ; then
        echo ", mount failed"
        exit -1
else
        echo -n ", mounted"
fi

if [[ ! -d usb/platform ]] ; then
        echo ", missing platform dir"
        exit -1
else
        echo ", OK"
fi

echo -n "Updating platform on boot device..."
if ! rsync -rltD "$platform_dir/" $tmp/platform.new/ ; then
        echo " failed"
        exit -1
else
        echo " OK"
fi

echo -n "Remounting boot device..."
umount "$usb" 2>/dev/null
if ! mount -F pcfs -o foldcase "$usb" "$tmp/usb" ; then
        echo " failed"
        exit -1
else
        echo " OK"
fi

echo -n "Verifying kernel checksum on boot device..."
openssl dgst -sha1 "$platform_dir"/i86pc/kernel/amd64/unix | cut -d ' ' -f 2 > kernel.expected
openssl dgst -sha1 $tmp/platform.new/i86pc/kernel/amd64/unix | cut -d ' ' -f 2 > kernel.actual
if ! cmp -s kernel.actual kernel.expected ; then
        echo " failed"
        exit -1
else
        echo " OK"
fi

echo -n "Verifying boot_archive checksum on boot device..."
openssl dgst -sha1 $tmp/platform.new/i86pc/amd64/boot_archive | cut -d ' ' -f 2 > boot_archive.actual
if ! cmp -s boot_archive.actual $tmp/platform.new/i86pc/amd64/boot_archive.hash ; then
        echo " failed"
        exit -1
else
        echo " OK"
fi

echo -n "Activating new platform on $usb... please wait..."
rm -rf $tmp/old
mkdir $tmp/old
if ! ( mv usb/platform $tmp/old && mv $tmp/platform.new usb/platform ) ; then
        echo " failed"
        exit -1
else
        echo "Finished: OK"
fi
echo
echo "Boot device upgraded. To do:"
echo
echo " 1) Sanity check the contents of $tmp/usb"
echo " 2) umount $usb"
echo " 3) reboot"
