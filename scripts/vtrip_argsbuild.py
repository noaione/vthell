import argparse

__YTDL_PATH__ = "/media/sdac/mizore/pip3/bin/youtube-dl"
__VTHELL_PATH__ = "/media/sdac/mizore/vthell"
__PROXY_URL__ = "http://178.63.231.130:14045"
__COOKIES_PATH__ = "/media/sdac/mizore/vthell/membercookies.txt"

h264_video = ["299", "137", "298", "136"]
vp9_video = ["303", "248", "302", "247"]
opus_audio = ["251"]
aac_audio = ["140"]

parser = argparse.ArgumentParser()
parser.add_argument("video_url")
parser.add_argument("-C", "--cookies", action="store_true", dest="cookie", help="Use cookies (provide path)")
parser.add_argument("-h264", "--force-h264", dest="avc_override", action="store_true", help="Force use H264 video.")
parser.add_argument("-aac", "--force-aac", dest="aac_override", action="store_true", help="Force use AAC audio.")
parser.add_argument("-p", "--proxy", action="store_true", dest="proxy", help="Use proxy")
parser.add_argument("-nk", "--no-keep", action="store_true", dest="nkeep", help="Dont keep original files.")
args = parser.parse_args()

main_video = []
if not args.avc_override:
    main_video.extend(vp9_video)
main_video.extend(h264_video)

main_audio = []
if not args.aac_override:
    main_audio.extend(opus_audio)
main_audio.extend(aac_audio)

ytdl_formats = []
for vcode in main_video:
    for acode in main_audio:
        dlcode = "{v}+{a}".format(v=vcode, a=acode)
        ytdl_formats.append(dlcode)

proxy_args = ""
if args.proxy:
    proxy_args += " --proxy {}".format(__PROXY_URL__)

cookies_args = ""
if args.cookie:
    cookies_args += " --cookies {}".format(__COOKIES_PATH__)

keep_args = " -k"
if args.nkeep:
    keep_args = ""

ytdl_format = "/".join(ytdl_formats)

extra_args = "{y} -f {f}".format(y=__YTDL_PATH__, f=ytdl_format)
extra_args += proxy_args
extra_args += cookies_args
extra_args += " --all-subs --embed-subs --convert-subs ass --merge-output-format mkv"
extra_args += keep_args
print(extra_args)  # Output to bash.