"""Per-language keyword anchors for field extraction.

Hindi/Gujarati terms below are drawn from common Indian retail-label usage (verified against
sample label wording during demo-data construction, per docs/LEGAL_REQUIREMENTS.md guidance to
not assume direct transliteration). Extend this list as demo_data samples reveal gaps — do not
guess new terms without checking against a real label first.
"""

MRP_ANCHORS = {
    "eng": ["mrp", "m.r.p", "maximum retail price", "retail price", "rs.", "rs", "₹", "price"],
    "hin": ["अधिकतम खुदरा मूल्य", "मूल्य", "एम.आर.पी"],
    "guj": ["મહત્તમ છૂટક કિંમત", "કિંમત"],
}

TAX_INCLUSIVE_ANCHORS = {
    "eng": ["incl. of all taxes", "inclusive of all taxes", "incl of all taxes", "including all taxes"],
    "hin": ["सभी करों सहित", "करों सहित"],
    "guj": ["તમામ કરવેરા સહિત"],
}

NET_QTY_ANCHORS = {
    "eng": ["net qty", "net quantity", "net wt", "net weight", "net vol", "net volume", "contents"],
    "hin": ["शुद्ध मात्रा", "शुद्ध वजन"],
    "guj": ["ચોખ્ખો જથ્થો", "ચોખ્ખું વજન"],
}

MFG_DATE_ANCHORS = {
    # "pkd" bare, not just "pkd on": real Indian packs overwhelmingly print the packing date as a
    # two-column row -- the label cell reads exactly "PKD." with the date in a separate value
    # column opposite (confirmed on a real DFM/Kurkure pack photo, where "pkd on" matched nothing
    # and a plainly printed packing date extracted as "not found"). Same 3-letter shape as the
    # "mfd"/"mfg" entries already here, and Rule 6(1)(d) treats the pre-packing date as
    # satisfying the declaration, so this anchors the right field.
    "eng": ["mfd", "mfg date", "mfg.date", "manufactured on", "packed on", "pkd on", "pkd", "mfg", "packing date"],
    "hin": ["निर्माण तिथि", "पैकिंग तिथि"],
    "guj": ["ઉત્પાદન તારીખ", "પેકિંગ તારીખ"],
}

BEST_BEFORE_ANCHORS = {
    "eng": ["best before", "use by", "expiry", "exp date", "exp.", "best before date"],
    "hin": ["सर्वोत्तम पहले", "उपयोग करें"],
    "guj": ["શ્રેષ્ઠ પહેલાં", "વાપરવાની છેલ્લી તારીખ"],
}

CONSUMER_CARE_ANCHORS = {
    "eng": ["consumer care", "customer care", "for complaints", "contact", "helpline", "toll free"],
    "hin": ["उपभोक्ता देखभाल", "ग्राहक सेवा"],
    "guj": ["ગ્રાહક સંભાળ"],
}

MANUFACTURER_ANCHORS = {
    "eng": ["manufactured by", "mfd by", "marketed by", "packed by", "manufacturer", "packer"],
    "hin": ["निर्माता", "द्वारा निर्मित", "द्वारा पैक"],
    "guj": ["ઉત્પાદક", "દ્વારા ઉત્પાદિત"],
}

COUNTRY_OF_ORIGIN_ANCHORS = {
    "eng": ["country of origin", "made in", "product of"],
    "hin": ["मूल देश", "में निर्मित"],
    "guj": ["મૂળ દેશ"],
}

UNIT_SALE_PRICE_ANCHORS = {
    "eng": ["unit sale price", "price per", "usp", "rs./kg", "rs./l"],
    "hin": ["इकाई विक्रय मूल्य"],
    "guj": ["એકમ વેચાણ કિંમત"],
}

ALL_ANCHOR_GROUPS = {
    "mrp": MRP_ANCHORS,
    "tax_inclusive": TAX_INCLUSIVE_ANCHORS,
    "net_qty": NET_QTY_ANCHORS,
    "mfg_date": MFG_DATE_ANCHORS,
    "best_before": BEST_BEFORE_ANCHORS,
    "consumer_care": CONSUMER_CARE_ANCHORS,
    "manufacturer": MANUFACTURER_ANCHORS,
    "country_of_origin": COUNTRY_OF_ORIGIN_ANCHORS,
    "unit_sale_price": UNIT_SALE_PRICE_ANCHORS,
}
