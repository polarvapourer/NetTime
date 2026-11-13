"""Windows data ACLs: current account and SYSTEM only, using the native API.

No chmod-based permission claims on Windows. Fail if ACLs cannot be applied.
"""
import ctypes
from ctypes import wintypes as W


def _api():
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ptr = ctypes.c_void_p
    adv.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)]
    adv.GetTokenInformation.argtypes = [W.HANDLE, ctypes.c_int, ptr, W.DWORD, ctypes.POINTER(W.DWORD)]
    adv.ConvertSidToStringSidW.argtypes = [ptr, ctypes.POINTER(W.LPWSTR)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [W.LPCWSTR, W.DWORD, ctypes.POINTER(ptr), ctypes.POINTER(W.DWORD)]
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [ptr, W.DWORD, W.DWORD, ctypes.POINTER(W.LPWSTR), ctypes.POINTER(W.DWORD)]
    adv.GetSecurityDescriptorDacl.argtypes = [ptr, ctypes.POINTER(W.BOOL), ctypes.POINTER(ptr), ctypes.POINTER(W.BOOL)]
    adv.SetNamedSecurityInfoW.argtypes = [W.LPWSTR, ctypes.c_int, W.DWORD, ptr, ptr, ptr, ptr]
    adv.SetNamedSecurityInfoW.restype = W.DWORD
    adv.GetNamedSecurityInfoW.argtypes = [W.LPCWSTR, ctypes.c_int, W.DWORD, ptr, ptr, ptr, ptr, ctypes.POINTER(ptr)]
    adv.GetNamedSecurityInfoW.restype = W.DWORD
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.LocalFree.argtypes = [ptr]
    kernel.LocalFree.restype = ptr
    return adv, kernel


def _check(good):
    if not good:
        raise ctypes.WinError(ctypes.get_last_error())


def current_sid():
    adv, kernel = _api()
    token = W.HANDLE()
    _check(adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)))
    try:
        size = W.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value)
        _check(adv.GetTokenInformation(token, 1, buf, size, ctypes.byref(size)))
        sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        text = W.LPWSTR()
        _check(adv.ConvertSidToStringSidW(sid, ctypes.byref(text)))
        try:
            return text.value
        finally:
            kernel.LocalFree(text)
    finally:
        kernel.CloseHandle(token)


def protect(path, directory=False):
    adv, kernel = _api()
    flags = "OICI" if directory else ""
    sddl = "D:P(A;%s;FA;;;SY)(A;%s;FA;;;%s)" % (flags, flags, current_sid())
    sd = ctypes.c_void_p()
    _check(adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(sd), None))
    try:
        present, defaulted, dacl = W.BOOL(), W.BOOL(), ctypes.c_void_p()
        _check(adv.GetSecurityDescriptorDacl(sd, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)))
        error = adv.SetNamedSecurityInfoW(str(path), 1, 4 | 0x80000000, None, None, dacl, None)
        if error:
            raise ctypes.WinError(error)
    finally:
        kernel.LocalFree(sd)


def private_ok(path):
    adv, kernel = _api()
    sd, text = ctypes.c_void_p(), W.LPWSTR()
    error = adv.GetNamedSecurityInfoW(str(path), 1, 4, None, None, None, None, ctypes.byref(sd))
    if error:
        raise ctypes.WinError(error)
    try:
        _check(adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd, 1, 4, ctypes.byref(text), None))
        try:
            # Compare complete protected DACL, ignoring only inheritance flags on the two ACEs.
            value = text.value.replace("OICI", "").replace("ID", "")
            expected = "D:P(A;;FA;;;SY)(A;;FA;;;%s)" % current_sid()
            return value == expected
        finally:
            kernel.LocalFree(text)
    finally:
        kernel.LocalFree(sd)
