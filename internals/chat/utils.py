"""
MIT License

Copyright (c) 2020-present xenova, noaione

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import re
from typing import Any, Optional

import pendulum

__all__ = (
    "try_get_first_key",
    "int_or_none",
    "float_or_none",
    "camel_case_split",
    "wrap_as_list",
    "remove_prefixes",
    "remove_suffixes",
    "arbg_int_to_rgba",
    "rgba_to_hex",
    "time_to_seconds",
    "seconds_to_time",
    "parse_expiry_as_date",
    "parse_iso8601",
    "float_or_none",
)


def try_get_first_key(dictionary, default=None):
    try:
        return next(iter(dictionary))
    except Exception:
        return default


def int_or_none(number: int, default: Optional[Any] = None):
    try:
        return int(number)
    except Exception:
        return default


def camel_case_split(word):
    return "_".join(re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", word)).lower()


def wrap_as_list(item):
    """Wraps an item in a list, if it is not already iterable
    :param item: The item to wrap
    :type item: object
    :return: The wrapped item
    :rtype: Union[list, tuple]
    """
    if not isinstance(item, (list, tuple)):
        item = [item]
    return item


def remove_prefixes(text, prefixes):
    for prefix in wrap_as_list(prefixes):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text


def remove_suffixes(text, suffixes):
    for suffix in wrap_as_list(suffixes):
        if text.endswith(suffix):
            text = text[0 : -len(suffix) :]
    return text


def arbg_int_to_rgba(argb_int):
    """Convert ARGB integer to RGBA array.
    :param argb_int: ARGB integer
    :type argb_int: int
    :return: RGBA array
    :rtype: list[int]
    """
    red = (argb_int >> 16) & 255
    green = (argb_int >> 8) & 255
    blue = argb_int & 255
    alpha = (argb_int >> 24) & 255
    return [red, green, blue, alpha]


def rgba_to_hex(colours):
    """Convert RGBA array to hex colour.
    :param colours: RGBA array
    :type colours: list[int]
    :return: Corresponding hexadecimal representation
    :rtype: str
    """
    return "#{:02x}{:02x}{:02x}{:02x}".format(*colours)


def time_to_seconds(time):
    """Convert timestamp string of the form 'hh:mm:ss' to seconds.
    :param time: Timestamp of the form 'hh:mm:ss'
    :type time: str
    :return: The corresponding number of seconds
    :rtype: int
    """
    if not time:
        return 0
    return int(
        sum(abs(int(x)) * 60 ** i for i, x in enumerate(reversed(time.replace(",", "").split(":"))))
        * (-1 if time[0] == "-" else 1)
    )


def seconds_to_time(seconds, format="{}:{:02}:{:02}", remove_leading_zeroes=True):
    """Convert seconds to timestamp.
    :param seconds: Number of seconds
    :type seconds: int
    :param format: The format string with elements representing hours, minutes and seconds. Defaults to '{}:{:02}:{:02}'
    :type format: str, optional
    :param remove_leading_zeroes: Whether to remove leading zeroes when seconds > 60, defaults to True
    :type remove_leading_zeroes: bool, optional
    :return: The corresponding timestamp string
    :rtype: str
    """
    h, remainder = divmod(abs(int(seconds)), 3600)
    m, s = divmod(remainder, 60)
    time_string = format.format(h, m, s)
    return ("-" if seconds < 0 else "") + (
        re.sub(r"^0:0?", "", time_string) if remove_leading_zeroes else time_string
    )


def parse_expiry_as_date(expiry: int):
    date = pendulum.from_timestamp(expiry)
    return date.format("ddd, DD MMM YYYY HH:mm:ss") + " GMT"


def parse_iso8601(date: str):
    if not date:
        return None
    as_pendulum = pendulum.parse(date)
    return as_pendulum.timestamp()


def float_or_none(data: Optional[float], default: Any = None):
    try:
        return float(data)
    except (ValueError, TypeError):
        return default
