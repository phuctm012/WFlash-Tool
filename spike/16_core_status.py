"""Spike 16: đọc trạng thái từng core (Session Explorer). CHỈ ĐỌC.

Vòng 9: flash chỉ được khi mọi core đang STOP; khi M7_0, A53, BBE32EP là NOT ACCESSIBLE
thì begin_program thất bại sau 5-9 s (Error loading monitor). Spike này tìm cách đọc trạng thái
đó qua isystem.connect để WFlash kiểm tra trước khi flash.

Không gọi reset, run, stop, begin_*, end, download, write, erase, set*. Không tạo
CMulticoreConnectionMgr (có thể mở thêm kết nối), chỉ in help của nó.
Chạy 2 lần: một lần khi mọi core STOP, một lần khi có core NOT ACCESSIBLE.
"""
import re

from _common import Report, base_args, connect, try_call

SOC = "/IDE/System.Debug.SoCs[0]"
GETTER = re.compile(r"^(get|is|has|status|name|num|count|size|core|soc|state|id|index)", re.IGNORECASE)
FORBIDDEN = re.compile(r"begin|end|program|reset|run|stop|set|write|erase|flush|download|load|attach|detach|connect|"
                       r"exec|step|halt|init|close|open|save|delete|remove|add|apply|wait", re.IGNORECASE)


def public(obj):
    return [n for n in dir(obj) if not n.startswith("_")]


def safe_getters(obj):
    """Zero-argument read-style methods only."""
    names = []
    for name in public(obj):
        if GETTER.match(name) and not FORBIDDEN.search(name) and callable(getattr(obj, name, None)):
            names.append(name)
    return names


def dump_object(report, obj, label, depth=0):
    """Print every getter of a status object, one level into returned objects and vectors."""
    report.line(f"{label}: type={type(obj).__name__} members={public(obj)}")
    for name in safe_getters(obj):
        try:
            value = getattr(obj, name)()
        except TypeError:
            continue  # needs arguments
        except Exception as exc:  # noqa: BLE001 - a probe reports everything
            report.line(f"  {label}.{name}() !! {exc}")
            continue
        report.line(f"  {label}.{name}() -> {value!r}")
        if depth == 0 and value is not None and not isinstance(value, (str, int, float, bool)):
            items = None
            try:
                items = list(value)
            except TypeError:
                pass
            if items is not None:
                for i, item in enumerate(items[:16]):
                    dump_object(report, item, f"{label}.{name}()[{i}]", depth + 1)
            else:
                dump_object(report, value, f"{label}.{name}()", depth + 1)


def main() -> None:
    parser = base_args(__doc__)
    parser.add_argument("--label", default="", help="Ghi chú trạng thái hiện tại, vd. all_stopped hoặc not_accessible")
    args = parser.parse_args()
    report = Report(f"16_core_status{'_' + args.label if args.label else ''}")
    try:
        ic, cmgr = connect(report, args.instance)
        report.line(f"label: {args.label!r}")

        report.section("cores in the workspace (scalar options)")
        ide = ic.CIDEController(cmgr)
        count = try_call(report, "Cores size", lambda: ide.getDynamicOptionSize(f"{SOC}.Cores"))
        for i in range(count or 0):
            try_call(report, f"Cores[{i}].Name", lambda i=i: ide.getOptionStr(f"{SOC}.Cores[{i}].Name"))

        report.section("CSessionCtrl.get_status")
        session = ic.CSessionCtrl(cmgr)
        status = try_call(report, "get_status", lambda: session.get_status())
        if status is not None:
            try:
                dump_object(report, status, "status")
            except Exception:
                report.exc("dump status")

        report.section("CDebugFacade default core")
        cpu = try_call(report, "getCPUStatus", lambda: ic.CDebugFacade(cmgr).getCPUStatus())
        if cpu is not None:
            try_call(report, "toString", lambda: cpu.toString())

        report.section("API surface for per-core access")
        report.line(f"ConnectionMgr core-ish: {[n for n in public(cmgr) if re.search('core|soc|multi', n, re.I)]}")
        report.line(f"CSessionCtrl: {public(session)}")
        report.line(f"ic names with Core/SoC/Session/Multicore: "
                    f"{[n for n in dir(ic) if re.search('core|soc|session|multicore', n, re.I)]}")
        for name in ("CDebugFacade", "CExecutionController", "CMulticoreConnectionMgr", "CSessionCtrl"):
            cls = getattr(ic, name, None)
            if cls is None:
                report.line(f"{name}: missing")
                continue
            report.line(f"--- {name}.__init__ ---")
            report.line(str(getattr(cls.__init__, "__doc__", None)))
        mcm = getattr(ic, "CMulticoreConnectionMgr", None)
        if mcm is not None:
            report.line(f"CMulticoreConnectionMgr members: {public(mcm)}")
            for name in public(mcm):
                doc = getattr(getattr(mcm, name), "__doc__", None)
                if doc:
                    report.line(f"  {name}: {doc.strip()[:400]}")
    except Exception:
        report.exc("spike 16")
    finally:
        report.close()


if __name__ == "__main__":
    main()
