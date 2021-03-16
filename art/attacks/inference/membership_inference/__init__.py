"""
Module providing membership inference attacks.
"""
from art.attacks.inference.membership_inference.black_box import MembershipInferenceBlackBox
from art.attacks.inference.membership_inference.black_box_rule_based import MembershipInferenceBlackBoxRuleBased
from art.attacks.inference.membership_inference.label_only_gap_attack import LabelOnlyGapAttack
from art.attacks.inference.membership_inference.label_only_boundary_distance import LabelOnlyDecisionBoundary
