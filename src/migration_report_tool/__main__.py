import multiprocessing

if (
    __name__ == "__main__"
    and multiprocessing.parent_process() is None
    and multiprocessing.current_process().name == "MainProcess"
):
    from .app.application import main

    multiprocessing.freeze_support()
    raise SystemExit(main())
