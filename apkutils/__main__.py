import binascii

from apkutils import APK


def main(args):
    apk = APK(args.p)

    if args.m:
        import json
        print(json.dumps(apk.get_manifest(), indent=1))

    elif args.s:
        for item in apk.get_strings():
            print(binascii.unhexlify(item).decode(errors='ignore'))

    elif args.f:
        for item in apk.get_files():
            print(item)


if __name__ == '__main__':
    __VERSION__ = '0.1.8'

    import argparse
    _parser = argparse.ArgumentParser(prog='adog', description=None)
    _parser.add_argument('p', help='path')
    _parser.add_argument('-m', action='store_true',
                         help='Show manifest', required=False)
    _parser.add_argument('-s', action='store_true',
                         help='Show strings', required=False)
    _parser.add_argument('-f', action='store_true',
                         help='Show files', required=False)

    _parser.add_argument('-V', '--version', action='version',
                         version=__VERSION__)

    _args = _parser.parse_args()
    main(_args)
