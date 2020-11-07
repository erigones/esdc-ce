#!/bin/bash

# https://github.com/calmh/smartos-platform-upgrade
# Copyright (c) 2012-2016 Jakob Borg & Contributors
# Distributed under the MIT License
#
# Modified to work on Danube cloud by Paolo Marcheschi
#

mkdir /zones/tmp
cert_file=$(mktemp)
function cleanup {
        rm "$cert_file"
}
trap cleanup EXIT
cat >"$cert_file" <<EOF
-----BEGIN CERTIFICATE-----
MIIF3jCCA8agAwIBAgIQAf1tMPyjylGoG7xkDjUDLTANBgkqhkiG9w0BAQwFADCB
iDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCk5ldyBKZXJzZXkxFDASBgNVBAcTC0pl
cnNleSBDaXR5MR4wHAYDVQQKExVUaGUgVVNFUlRSVVNUIE5ldHdvcmsxLjAsBgNV
BAMTJVVTRVJUcnVzdCBSU0EgQ2VydGlmaWNhdGlvbiBBdXRob3JpdHkwHhcNMTAw
MjAxMDAwMDAwWhcNMzgwMTE4MjM1OTU5WjCBiDELMAkGA1UEBhMCVVMxEzARBgNV
BAgTCk5ldyBKZXJzZXkxFDASBgNVBAcTC0plcnNleSBDaXR5MR4wHAYDVQQKExVU
aGUgVVNFUlRSVVNUIE5ldHdvcmsxLjAsBgNVBAMTJVVTRVJUcnVzdCBSU0EgQ2Vy
dGlmaWNhdGlvbiBBdXRob3JpdHkwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIK
AoICAQCAEmUXNg7D2wiz0KxXDXbtzSfTTK1Qg2HiqiBNCS1kCdzOiZ/MPans9s/B
3PHTsdZ7NygRK0faOca8Ohm0X6a9fZ2jY0K2dvKpOyuR+OJv0OwWIJAJPuLodMkY
tJHUYmTbf6MG8YgYapAiPLz+E/CHFHv25B+O1ORRxhFnRghRy4YUVD+8M/5+bJz/
Fp0YvVGONaanZshyZ9shZrHUm3gDwFA66Mzw3LyeTP6vBZY1H1dat//O+T23LLb2
VN3I5xI6Ta5MirdcmrS3ID3KfyI0rn47aGYBROcBTkZTmzNg95S+UzeQc0PzMsNT
79uq/nROacdrjGCT3sTHDN/hMq7MkztReJVni+49Vv4M0GkPGw/zJSZrM233bkf6
c0Plfg6lZrEpfDKEY1WJxA3Bk1QwGROs0303p+tdOmw1XNtB1xLaqUkL39iAigmT
Yo61Zs8liM2EuLE/pDkP2QKe6xJMlXzzawWpXhaDzLhn4ugTncxbgtNMs+1b/97l
c6wjOy0AvzVVdAlJ2ElYGn+SNuZRkg7zJn0cTRe8yexDJtC/QV9AqURE9JnnV4ee
UB9XVKg+/XRjL7FQZQnmWEIuQxpMtPAlR1n6BB6T1CZGSlCBst6+eLf8ZxXhyVeE
Hg9j1uliutZfVS7qXMYoCAQlObgOK6nyTJccBz8NUvXt7y+CDwIDAQABo0IwQDAd
BgNVHQ4EFgQUU3m/WqorSs9UgOHYm8Cd8rIDZsswDgYDVR0PAQH/BAQDAgEGMA8G
A1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQEMBQADggIBAFzUfA3P9wF9QZllDHPF
Up/L+M+ZBn8b2kMVn54CVVeWFPFSPCeHlCjtHzoBN6J2/FNQwISbxmtOuowhT6KO
VWKR82kV2LyI48SqC/3vqOlLVSoGIG1VeCkZ7l8wXEskEVX/JJpuXior7gtNn3/3
ATiUFJVDBwn7YKnuHKsSjKCaXqeYalltiz8I+8jRRa8YFWSQEg9zKC7F4iRO/Fjs
8PRF/iKz6y+O0tlFYQXBl2+odnKPi4w2r78NBc5xjeambx9spnFixdjQg3IM8WcR
iQycE0xyNN+81XHfqnHd4blsjDwSXWXavVcStkNr/+XeTWYRUc+ZruwXtuhxkYze
Sf7dNXGiFSeUHM9h4ya7b6NnJSFd5t0dCy5oGzuCr+yDZ4XUmFF0sbmZgIn/f3gZ
XHlKYC6SQK5MNyosycdiyA5d9zZbyuAlJQG03RoHnHcAP9Dc1ew91Pq7P8yF1m9/
qS3fuQL39ZeatTXaw2ewh0qpKJ4jjv9cJ2vhsE/zB+4ALtRZh8tSQZXq9EfX7mRB
VXyNWQKV3WKdwrnuWih0hKWbt5DHDAff9Yk2dDLWKMGwsAvgnEzDHNb842m1R0aB
L6KCq9NjRHDEjf8tM7qtj3u1cIiuPhnPQCjY/MiQu12ZIvVS5ljFH4gxQ+6IHdfG
jjxDah2nGN59PRbxYvnKkKj9
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIGEzCCA/ugAwIBAgIQfVtRJrR2uhHbdBYLvFMNpzANBgkqhkiG9w0BAQwFADCB
iDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCk5ldyBKZXJzZXkxFDASBgNVBAcTC0pl
cnNleSBDaXR5MR4wHAYDVQQKExVUaGUgVVNFUlRSVVNUIE5ldHdvcmsxLjAsBgNV
BAMTJVVTRVJUcnVzdCBSU0EgQ2VydGlmaWNhdGlvbiBBdXRob3JpdHkwHhcNMTgx
MTAyMDAwMDAwWhcNMzAxMjMxMjM1OTU5WjCBjzELMAkGA1UEBhMCR0IxGzAZBgNV
BAgTEkdyZWF0ZXIgTWFuY2hlc3RlcjEQMA4GA1UEBxMHU2FsZm9yZDEYMBYGA1UE
ChMPU2VjdGlnbyBMaW1pdGVkMTcwNQYDVQQDEy5TZWN0aWdvIFJTQSBEb21haW4g
VmFsaWRhdGlvbiBTZWN1cmUgU2VydmVyIENBMIIBIjANBgkqhkiG9w0BAQEFAAOC
AQ8AMIIBCgKCAQEA1nMz1tc8INAA0hdFuNY+B6I/x0HuMjDJsGz99J/LEpgPLT+N
TQEMgg8Xf2Iu6bhIefsWg06t1zIlk7cHv7lQP6lMw0Aq6Tn/2YHKHxYyQdqAJrkj
eocgHuP/IJo8lURvh3UGkEC0MpMWCRAIIz7S3YcPb11RFGoKacVPAXJpz9OTTG0E
oKMbgn6xmrntxZ7FN3ifmgg0+1YuWMQJDgZkW7w33PGfKGioVrCSo1yfu4iYCBsk
Haswha6vsC6eep3BwEIc4gLw6uBK0u+QDrTBQBbwb4VCSmT3pDCg/r8uoydajotY
uK3DGReEY+1vVv2Dy2A0xHS+5p3b4eTlygxfFQIDAQABo4IBbjCCAWowHwYDVR0j
BBgwFoAUU3m/WqorSs9UgOHYm8Cd8rIDZsswHQYDVR0OBBYEFI2MXsRUrYrhd+mb
+ZsF4bgBjWHhMA4GA1UdDwEB/wQEAwIBhjASBgNVHRMBAf8ECDAGAQH/AgEAMB0G
A1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAbBgNVHSAEFDASMAYGBFUdIAAw
CAYGZ4EMAQIBMFAGA1UdHwRJMEcwRaBDoEGGP2h0dHA6Ly9jcmwudXNlcnRydXN0
LmNvbS9VU0VSVHJ1c3RSU0FDZXJ0aWZpY2F0aW9uQXV0aG9yaXR5LmNybDB2Bggr
BgEFBQcBAQRqMGgwPwYIKwYBBQUHMAKGM2h0dHA6Ly9jcnQudXNlcnRydXN0LmNv
bS9VU0VSVHJ1c3RSU0FBZGRUcnVzdENBLmNydDAlBggrBgEFBQcwAYYZaHR0cDov
L29jc3AudXNlcnRydXN0LmNvbTANBgkqhkiG9w0BAQwFAAOCAgEAMr9hvQ5Iw0/H
ukdN+Jx4GQHcEx2Ab/zDcLRSmjEzmldS+zGea6TvVKqJjUAXaPgREHzSyrHxVYbH
7rM2kYb2OVG/Rr8PoLq0935JxCo2F57kaDl6r5ROVm+yezu/Coa9zcV3HAO4OLGi
H19+24rcRki2aArPsrW04jTkZ6k4Zgle0rj8nSg6F0AnwnJOKf0hPHzPE/uWLMUx
RP0T7dWbqWlod3zu4f+k+TY4CFM5ooQ0nBnzvg6s1SQ36yOoeNDT5++SR2RiOSLv
xvcRviKFxmZEJCaOEDKNyJOuB56DPi/Z+fVGjmO+wea03KbNIaiGCpXZLoUmGv38
sbZXQm2V0TP2ORQGgkE49Y9Y3IBbpNV9lXj9p5v//cWoaasm56ekBYdbqbe4oyAL
l6lFhd2zi+WJN44pDfwGF/Y4QA5C5BIG+3vzxhFoYt/jmPQT2BVPi7Fp2RBgvGQq
6jG35LWjOhSbJuMLe/0CjraZwTiXWTb2qHSihrZe68Zk6s+go/lunrotEbaGmAhY
LcmsJWTyXnW0OMGuf1pGg+pRyrbxmRE1a6Vqe8YAsOf4vmSyrcjC8azjUeqkk+B5
yOGBQMkKW+ESPMFgKuOXwIlCypTPRpgSabuY0MLTDXJLR27lk8QyKGOHQ+SwMj4K
00u/I5sUKUErmgQfky3xxzlIPK1aEn8=
-----END CERTIFICATE-----
EOF

function _curl {
        curl -s --cacert "$cert_file" $@
}
function usage() {
    cat <<- "USAGE"
$ platform-upgrade [-u URL -s MD5SUM_URL] [-f]

OPTIONS:
  -u URL        : Remote/local url of platform-version.tgz file
  -s MD5SUM_URL : Remote/local url of md5 checksum file
  -f            : Force installation if version is already present

EXAMPLE:
  # Use default Joyent URL for latest platform image
  platform-upgrade
  # Use local platform and checksum file
  platform-upgrade -u file:///tmp/platform-20180510T153535Z.tgz -s file:///tmp/md5sum.txt
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

if [[ -n $platform_url ]] && [[ ! -n $md5sums_url ]]; then
	usage
	exit -1
fi

if [[ ! -n $platform_url ]]; then
    host=https://us-east.manta.joyent.com
    latest_path="${host}$(_curl "$host/Joyent_Dev/public/SmartOS/latest")"
    version="$(expr "$latest_path" : '.*\([0-9]\{8\}T[0-9]\{6\}Z\).*')"
    latest_spec_path="$(_curl "$host/Joyent_Dev/public/SmartOS/$version")"
    header="$(expr "$latest_spec_path" : '.*platform-release-\([0-9]\{8\}\)-.*')"
    platform_url="$latest_path/platform-release-$header-$version.tgz"
    if [[ ! -n $md5sums_url ]]; then
        md5sums_url="$latest_path/md5sums.txt"
    fi
else
    header="$(expr "$platform_url" : '.*platform-\([0-9]\{8\}\)-.*')"
    version="$(expr "$platform_url" : '.*\([0-9]\{8\}T[0-9]\{6\}Z\).*')"
fi

platform_file="platform-$version.tgz"
platform_dir="platform-$version"

IFS=_ read brand kernel < <(uname -v)
echo " brand="  $brand 
echo "Actual kernel= " $kernel
echo "New Version= " $version
if [[ $kernel == $version ]]; then
    echo "Already on latest version ($kernel)."
    $force || exit -1
fi

tmp=$(mktemp -d -p /zones/tmp -t)
cd "$tmp" || exit -1

echo -n "Downloading $platform_file..."
if ! _curl -o "$platform_file" "$platform_url" ; then
        echo " failed"
        exit -1
else
        echo " OK"
fi

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
