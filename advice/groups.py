"""Test group assignment. One pure function, used by the tool, the suppression writer and the result reader."""
import hashlib


def group_of(merchant_id, sold_out_date, share):
    """'B' (new routing) or 'A' (current routing) for one merchant in one ISO week.

    SHA-256 of "<merchant id>|<ISO year>-W<week>", first 8 hex digits as an integer, divided by 2^32.
    B if the result is below `share`. Share 0 gives all A. Every deal of a merchant in a week lands in one group.
    """
    year, week, _ = sold_out_date.isocalendar()
    digest = hashlib.sha256(f"{merchant_id}|{year}-W{week:02d}".encode()).hexdigest()
    return "B" if int(digest[:8], 16) / 2 ** 32 < share else "A"
