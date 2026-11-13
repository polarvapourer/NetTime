"""Windows data ACLs: current account and SYSTEM only, using the native API.

No chmod-based permission claims on Windows. Fail if ACLs cannot be applied.
"""
import ctypes
import os
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
    adv.GetSecurityDescriptorControl.argtypes = [ptr, ctypes.POINTER(W.WORD), ctypes.POINTER(W.DWORD)]
    adv.GetAclInformation.argtypes = [ptr, ptr, W.DWORD, ctypes.c_int]
    adv.GetAce.argtypes = [ptr, W.DWORD, ctypes.POINTER(ptr)]
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
    sd, dacl = ctypes.c_void_p(), ctypes.c_void_p()
    error = adv.GetNamedSecurityInfoW(str(path), 1, 4, None, None, ctypes.byref(dacl), None, ctypes.byref(sd))
    if error:
        raise ctypes.WinError(error)
    try:
        control, revision = W.WORD(), W.DWORD()
        _check(adv.GetSecurityDescriptorControl(sd, ctypes.byref(control), ctypes.byref(revision)))
        if not dacl or not control.value & 0x1000:  # SE_DACL_PROTECTED; no inherited broad grants
            return False
        class AclSize(ctypes.Structure):
            _fields_ = [('count', W.DWORD), ('used', W.DWORD), ('free', W.DWORD)]
        size = AclSize()
        _check(adv.GetAclInformation(dacl, ctypes.byref(size), ctypes.sizeof(size), 2))
        wanted = {current_sid(), 'S-1-5-18'}  # this account and SYSTEM
        seen = set()
        for index in range(size.count):
            ace = ctypes.c_void_p()
            _check(adv.GetAce(dacl, index, ctypes.byref(ace)))
            address = ace.value
            kind = ctypes.c_ubyte.from_address(address).value
            flags = ctypes.c_ubyte.from_address(address + 1).value
            mask = W.DWORD.from_address(address + 4).value
            if kind != 0 or mask != 0x1f01ff or flags & 0x0c:  # full allow ACE, applies to this object
                return False
            if os.path.isdir(path) and flags & 3 != 3:  # child files must inherit protection
                return False
            text = W.LPWSTR()
            _check(adv.ConvertSidToStringSidW(ctypes.c_void_p(address + 8), ctypes.byref(text)))
            try:
                sid = text.value
                if sid not in wanted:
                    return False
                seen.add(sid)
            finally:
                kernel.LocalFree(text)
        return seen == wanted
    finally:
        kernel.LocalFree(sd)
