# Native file browser sizes

Run from the source root:

    python3 tools/native_file_sizes_test/run_tests.py
    python3 tools/fs_stage1_test/run_tests.py
    python3 tools/menu_theme_test/run_tests.py

The listing still uses its original protected opendir/readdir/closedir path.
The new bmc64_directory_entry_size accessor copies no file contents and performs
no I/O: it returns FatFs fsize cached on the same open iterator. It cannot return
another iterator's metadata and is invalid after directory entries, rewind,
EOF, errors, close or slot reuse. No dirent layout/ABI changes were made.

Included file nodes cache the formatted size in the existing displayed_value.
Their full filenames remain in str_value. Existing sorting runs before labels
are shortened, so the display-only ellipsis cannot reorder entries. Extensions
are retained where they fit, and truncation respects UTF-8 character boundaries,
the label's byte capacity and 8px CHARGEN cells. At least one blank cell separates
the label from the right-aligned size. Folder (dir) labels are unchanged.

Units: 0..1023 bytes use B; larger values follow the actual Web formatter's
ceil-to-KB and decimal MB/GB rules. Integer arithmetic handles UINT32_MAX without
overflow. 217 values are compared with the actual JavaScript formatter, covering
boundaries, rounding ties and deterministic random values.

The host listing test executes production formatting, listing, sorting, full
selection/path restoration, metadata cache and directory-reader functions with
in-memory FatFs fixtures. It covers 2000 entries, SD/USB/USB2/USB3 paths,
independent iterators, long UTF-8 names, identical shortened labels, extensions,
filters, parent controls, errors, read counts and cached-row/selection work.
Existing renderer tests exercise the actual row renderer's right alignment,
selection colors/highlight geometry and scrolled positions. The shared renderer,
Web UI, loading callbacks and filesystem write paths are unchanged.

No live media is used. Pi visual/USB smoke testing remains recommended.
