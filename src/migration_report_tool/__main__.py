import multiprocessing

from .app.application import main

multiprocessing.freeze_support()
raise SystemExit(main())
