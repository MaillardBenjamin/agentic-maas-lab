package maas

import rego.v1

default allow := false

allow if {
    input.action == "refund"
    input.principal.org == input.org
    input.principal.role == "clerk"
    input.amount_cents > 0
    input.amount_cents <= 500
}

allow if {
    input.action == "refund"
    input.principal.org == input.org
    input.principal.role == "supervisor"
    input.amount_cents > 0
    input.amount_cents <= 100000
}
