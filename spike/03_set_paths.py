"""Spike 03: đổi giá trị một option URL, đọc lại, rồi khôi phục giá trị cũ."""
from _common import Report, base_args, connect, try_call


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--url", required=True, action="append", help="Option URL (từ kết quả 02)")
    parser.add_argument("--new-path", required=True, action="append", help="Giá trị mới, cùng thứ tự với --url")
    parser.add_argument("--keep", action="store_true", help="Không khôi phục giá trị cũ")
    args = parser.parse_args()
    report = Report("03_set_paths")
    try:
        ic, cmgr = connect(report, args.instance)
        ide = ic.CIDEController(cmgr)
        for url, new in zip(args.url, args.new_path):
            report.section(url)
            old = try_call(report, "read old", lambda: ide.getOptionStr(url))
            try_call(report, "setOption(new)", lambda: ide.setOption(url, new))
            try_call(report, "read back", lambda: ide.getOptionStr(url))
            if not args.keep and old is not None:
                try_call(report, "restore old", lambda: ide.setOption(url, old))
                try_call(report, "read after restore", lambda: ide.getOptionStr(url))
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
