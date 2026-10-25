package maas_test

import rego.v1
import data.maas

test_clerk_allowed if {
    maas.allow with input as {"action":"refund","org":"alize","amount_cents":200,"principal":{"org":"alize","role":"clerk"}}
}
test_clerk_over_limit_denied if {
    not maas.allow with input as {"action":"refund","org":"alize","amount_cents":600,"principal":{"org":"alize","role":"clerk"}}
}
test_cross_org_denied if {
    not maas.allow with input as {"action":"refund","org":"other","amount_cents":200,"principal":{"org":"alize","role":"supervisor"}}
}
test_traveler_denied if {
    not maas.allow with input as {"action":"refund","org":"alize","amount_cents":1,"principal":{"org":"alize","role":"traveler"}}
}
test_unknown_action_denied if {
    not maas.allow with input as {"action":"load","org":"alize","amount_cents":1,"principal":{"org":"alize","role":"supervisor"}}
}
