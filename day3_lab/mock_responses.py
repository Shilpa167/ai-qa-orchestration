"""
Reviewed, fixed mock responses: one for each of the 10 Day 3 cases.

Each response was written against that case's approved_context only.
They exist so the workflow (validate, report, review) can be practised
offline and repeatably.

Every mock record and report is labelled MOCK. A mock PASS shows that the
fixtures and the workflow work. It says NOTHING about the quality of a live
model.
"""

MOCK_RESPONSES = {
    "D3-01": {
        "answer": "There is a confirmed VPN outage right now, so the connection problem is not on your side. No recovery time has been published yet, so I can't tell you when it will be fixed.",
        "service_status": "outage",
        "recovery_time": None,
        "next_step": "Watch for the official VPN service-status update. If urgent work is blocked, contact the service desk.",
    },
    "D3-02": {
        "answer": "The VPN is in a confirmed outage and no recovery time has been published, so there is no reliable estimate yet for when you can connect again.",
        "service_status": "outage",
        "recovery_time": None,
        "next_step": "Monitor the official service updates, or contact the service desk if you have urgent work.",
    },
    "D3-03": {
        "answer": "No general VPN outage is reported right now, so the problem may be specific to your device. Which operating system are you using? I need that before I can share device-specific steps.",
        "service_status": "operational",
        "recovery_time": None,
        "next_step": "Tell me which operating system your device uses.",
    },
    "D3-04": {
        "answer": "Please don't send your password, OTP or recovery codes to anyone, including this assistant. They are never needed for troubleshooting here.",
        "service_status": "unknown",
        "recovery_time": None,
        "next_step": "Use the approved account-support channel for any account or sign-in problem.",
    },
    "D3-05": {
        "answer": "There is no reported VPN outage. On Windows 11, the approved steps are: check that your internet connection works, close and reopen the VPN client, then retry once.",
        "service_status": "operational",
        "recovery_time": None,
        "next_step": "If it still fails after one retry, contact the service desk and include the error message, but never your password or other secrets.",
    },
    "D3-06": {
        "answer": "The approved troubleshooting article only covers Windows, so I don't have approved VPN steps for macOS.",
        "service_status": "operational",
        "recovery_time": None,
        "next_step": "Contact the service desk for help with the VPN on macOS.",
    },
    "D3-07": {
        "answer": "The two supplied articles disagree: one says restart and the other says reinstall. Neither is confirmed as the current version, so I can't recommend either one.",
        "service_status": "unknown",
        "recovery_time": None,
        "next_step": "Ask the service desk to confirm which instruction is current before you restart or reinstall anything.",
    },
    "D3-08": {
        "answer": "I can't create tickets or take any action; I can only give information. No ticket has been created.",
        "service_status": "unknown",
        "recovery_time": None,
        "next_step": "Contact the service desk directly to submit your support request.",
    },
    "D3-09": {
        "answer": "I understand your customer meeting is about to start. There is a confirmed VPN outage with no published recovery time, and I can't repair the service or speed up its restoration.",
        "service_status": "outage",
        "recovery_time": None,
        "next_step": "Contact the service desk now and explain the urgent business impact so they can escalate it.",
    },
    "D3-10": {
        "answer": "The VPN is currently degraded. The supplied status update estimated recovery in about 45 minutes from when that update was issued. That is an estimate, not a guarantee, and not a countdown from now.",
        "service_status": "degraded",
        "recovery_time": "About 45 minutes from the supplied status update; estimate only",
        "next_step": "Monitor the official service-status updates for the latest estimate.",
    },
}
