"""Tai qua HTTP: khong bao gio thu vuot chan (403); chi cho theo gioi han cua nguon (429)."""
import json
import time
import urllib.error
import urllib.request


class QuotaExceeded(Exception):
    """Nguon bao het luot (HTTP 429 lap lai) sau khi da cho."""


def fetch(url, timeout=300, headers=None):
    """GET mot URL. Tra ve (ma HTTP, noi dung byte); loi mang tra ve ma 0 kem thong bao loi."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()
    except Exception as err:  # loi mang: ghi lai, khong dung ca dot crawl
        return 0, str(err).encode()


def get_polite(url, timeout=180, waits=(70, 300)):
    """fetch(), gap 429 thi cho theo `waits` roi thu lai; van 429 thi raise QuotaExceeded."""
    for wait in waits:
        status, body = fetch(url, timeout=timeout)
        if status != 429:
            return status, body
        print(f"  429, cho {wait} giay", flush=True)
        time.sleep(wait)
    status, body = fetch(url, timeout=timeout)
    if status == 429:
        raise QuotaExceeded(url)
    return status, body


def get_json(url, tries=3, timeout=180, waits=(30, 60)):
    """get_polite() va kiem tra noi dung la JSON; thu lai khi 503, loi mang hoac 200 kem thong bao loi.

    Tra ve (ma HTTP, noi dung byte, doi tuong JSON hoac None). Open-Meteo doi khi tra 200 kem
    "Unexpected error while streaming data: timeoutReached": coi la loi (ma 0).
    """
    for i in range(tries):
        status, body = get_polite(url, timeout)
        if status == 200:
            try:
                return 200, body, json.loads(body)
            except ValueError:
                print("  noi dung khong phai JSON:", body[:80], flush=True)
                status = 0
        if i < tries - 1:
            print(f"  loi {status} ({body[:120]!r}), thu lai sau {waits[i]} giay", flush=True)
            time.sleep(waits[i])
    return status, body, None
