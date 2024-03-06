import os
import threading

import pytest

from memray import FileDestination
from memray import FileReader
from memray import Tracker
from memray._test import MemoryAllocator


def test_rejects_different_header_magic(tmp_path):
    # GIVEN
    output = tmp_path / "test.bin"
    allocator = MemoryAllocator()

    # WHEN
    # Create a valid allocation record file
    with Tracker(output):
        allocator.valloc(1024)

    # Change the header magic (same length as "memray")
    with output.open("rb+") as f:
        f.write(b"badxxx")

    # THEN
    with pytest.raises(
        OSError, match="does not look like a binary generated by memray"
    ):
        FileReader(output).get_allocation_records()


def test_rejects_different_header_version(tmp_path):
    # GIVEN
    output = tmp_path / "test.bin"
    allocator = MemoryAllocator()

    # WHEN
    # Create a valid allocation record file
    destination = FileDestination(output, overwrite=False, compress_on_exit=False)
    with Tracker(destination=destination):
        allocator.valloc(1024)

    # Change the header version to zero
    with output.open("rb+") as f:
        f.seek(7)
        f.write(b"\0")

    # THEN
    with pytest.raises(OSError, match="incompatible with this version"):
        FileReader(output).get_allocation_records()


def test_filereader_fails_to_open_file(tmp_path):
    """This checks that we throw in the FileSource C++ ctor when we fail to open the stream."""
    # GIVEN
    test_file = tmp_path / "test.bin"
    test_file.touch(mode=000)

    try:
        test_file.read_text()
    except OSError:
        pass
    else:  # pragma: no cover
        pytest.skip("The current user can ignore file permissions")

    # WHEN/THEN
    with pytest.raises(OSError, match="Could not open file"):
        FileReader(test_file)


def test_read_pid(tmp_path):
    # GIVEN
    output = tmp_path / "test.bin"
    allocator = MemoryAllocator()

    # WHEN
    with Tracker(output):
        allocator.valloc(1024)

    # THEN
    assert FileReader(output).metadata.pid == os.getpid()


def test_read_tid(tmp_path):
    # GIVEN
    output = tmp_path / "test.bin"
    allocator = MemoryAllocator()

    def func():
        allocator.valloc(1024)

    # WHEN
    t = threading.Thread(target=func)
    with Tracker(output):
        func()
        t.start()
        t.join()

    # THEN
    reader = FileReader(output)
    main_tid = reader.metadata.main_thread_id
    all_allocations = reader.get_allocation_records()
    all_tids = tuple(allocation.tid for allocation in all_allocations)
    assert main_tid in set(all_tids)
    # The main thread should be the first one in the list
    assert main_tid == all_tids[0]
