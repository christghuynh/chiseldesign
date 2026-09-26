"""Tunable hardware and tax constants for the shopping list (GEO-13).

Every value here is a PLACEHOLDER to confirm with a real builder / retailer (task NC-4). Change them
here only; the pricing code reads nothing else.
"""

# PLACEHOLDER (NC-4): deck screws driven where one deck board crosses one supporting member.
DECK_SCREWS_PER_CROSSING = 2

# PLACEHOLDER (NC-4): joist hangers per joist end, so 2 per joist (one at each end).
JOIST_HANGERS_PER_JOIST_END = 1
JOIST_ENDS = 2

# PLACEHOLDER (NC-4): one post base per 4x4 post.
POST_BASES_PER_POST = 1

# PLACEHOLDER (NC-4): structural screws fixing each joist hanger.
STRUCTURAL_SCREWS_PER_HANGER = 8

# PLACEHOLDER (NC-4): a build that uses a fastener type always buys at least this many boxes of it.
MIN_BOXES_PER_FASTENER = 1

# Ontario HST (CAD); confirm the rate for the build's province.
HST_RATE = 0.13

# Part names the pricing rules key on (the templates' names).
SUPPORT_NAMES = ("Stringer", "Landing joist")  # members a deck board is screwed to
JOIST_NAME = "Landing joist"
DECK_BOARD_NAMES = ("deck board", "tread board")  # case-insensitive "contains": ramp decking, landing decking, step treads
# Posts that stand on a post base. Not garden-bed corner posts or workbench legs, which need none.
POST_BASE_NAMES = ("Handrail post", "Landing post")
POST_MATERIAL = "4x4_PT"

# prices.json keys for the hardware lines
DECK_SCREWS_KEY = "deck_screws_box"
STRUCTURAL_SCREWS_KEY = "structural_screws_box"
JOIST_HANGER_KEY = "joist_hanger"
POST_BASE_KEY = "post_base"
# Order of the hardware lines on the list, after the lumber.
HARDWARE_ORDER = (DECK_SCREWS_KEY, JOIST_HANGER_KEY, POST_BASE_KEY, STRUCTURAL_SCREWS_KEY)
