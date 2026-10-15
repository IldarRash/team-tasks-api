var stats = {
    type: "GROUP",
name: "All Requests",
path: "",
pathFormatted: "group_missing-name--1146707516",
stats: {
    "name": "All Requests",
    "numberOfRequests": {
        "total": "25372",
        "ok": "25372",
        "ko": "0"
    },
    "minResponseTime": {
        "total": "2",
        "ok": "2",
        "ko": "-"
    },
    "maxResponseTime": {
        "total": "4884",
        "ok": "4884",
        "ko": "-"
    },
    "meanResponseTime": {
        "total": "235",
        "ok": "235",
        "ko": "-"
    },
    "standardDeviation": {
        "total": "349",
        "ok": "349",
        "ko": "-"
    },
    "percentiles1": {
        "total": "91",
        "ok": "91",
        "ko": "-"
    },
    "percentiles2": {
        "total": "263",
        "ok": "263",
        "ko": "-"
    },
    "percentiles3": {
        "total": "962",
        "ok": "956",
        "ko": "-"
    },
    "percentiles4": {
        "total": "1741",
        "ok": "1706",
        "ko": "-"
    },
    "group1": {
    "name": "t < 800 ms",
    "htmlName": "t < 800 ms",
    "count": 23545,
    "percentage": 92.79914866782279
},
    "group2": {
    "name": "800 ms <= t < 1200 ms",
    "htmlName": "t >= 800 ms <br> t < 1200 ms",
    "count": 1108,
    "percentage": 4.36701876083872
},
    "group3": {
    "name": "t >= 1200 ms",
    "htmlName": "t >= 1200 ms",
    "count": 719,
    "percentage": 2.8338325713384833
},
    "group4": {
    "name": "failed",
    "htmlName": "failed",
    "count": 0,
    "percentage": 0.0
},
    "meanNumberOfRequestsPerSecond": {
        "total": "415.93",
        "ok": "415.93",
        "ko": "-"
    }
},
contents: {
"group_task-lifecycle--1543984465": {
          type: "GROUP",
name: "Task lifecycle",
path: "Task lifecycle",
pathFormatted: "group_task-lifecycle--1543984465",
stats: {
    "name": "Task lifecycle",
    "numberOfRequests": {
        "total": "6343",
        "ok": "6343",
        "ko": "0"
    },
    "minResponseTime": {
        "total": "111",
        "ok": "111",
        "ko": "-"
    },
    "maxResponseTime": {
        "total": "5926",
        "ok": "5926",
        "ko": "-"
    },
    "meanResponseTime": {
        "total": "941",
        "ok": "941",
        "ko": "-"
    },
    "standardDeviation": {
        "total": "704",
        "ok": "704",
        "ko": "-"
    },
    "percentiles1": {
        "total": "735",
        "ok": "735",
        "ko": "-"
    },
    "percentiles2": {
        "total": "1253",
        "ok": "1253",
        "ko": "-"
    },
    "percentiles3": {
        "total": "2321",
        "ok": "2321",
        "ko": "-"
    },
    "percentiles4": {
        "total": "3290",
        "ok": "3319",
        "ko": "-"
    },
    "group1": {
    "name": "t < 800 ms",
    "htmlName": "t < 800 ms",
    "count": 3401,
    "percentage": 53.61816175311367
},
    "group2": {
    "name": "800 ms <= t < 1200 ms",
    "htmlName": "t >= 800 ms <br> t < 1200 ms",
    "count": 1209,
    "percentage": 19.06038152293867
},
    "group3": {
    "name": "t >= 1200 ms",
    "htmlName": "t >= 1200 ms",
    "count": 1733,
    "percentage": 27.321456723947655
},
    "group4": {
    "name": "failed",
    "htmlName": "failed",
    "count": 0,
    "percentage": 0.0
},
    "meanNumberOfRequestsPerSecond": {
        "total": "103.98",
        "ok": "103.98",
        "ko": "-"
    }
},
contents: {
"req_create-task-1116105225": {
        type: "REQUEST",
        name: "Create task",
path: "Task lifecycle / Create task",
pathFormatted: "req_task-lifecycle---1308145689",
stats: {
    "name": "Create task",
    "numberOfRequests": {
        "total": "6343",
        "ok": "6343",
        "ko": "0"
    },
    "minResponseTime": {
        "total": "5",
        "ok": "5",
        "ko": "-"
    },
    "maxResponseTime": {
        "total": "3535",
        "ok": "3535",
        "ko": "-"
    },
    "meanResponseTime": {
        "total": "240",
        "ok": "240",
        "ko": "-"
    },
    "standardDeviation": {
        "total": "355",
        "ok": "355",
        "ko": "-"
    },
    "percentiles1": {
        "total": "87",
        "ok": "87",
        "ko": "-"
    },
    "percentiles2": {
        "total": "259",
        "ok": "259",
        "ko": "-"
    },
    "percentiles3": {
        "total": "990",
        "ok": "990",
        "ko": "-"
    },
    "percentiles4": {
        "total": "1769",
        "ok": "1777",
        "ko": "-"
    },
    "group1": {
    "name": "t < 800 ms",
    "htmlName": "t < 800 ms",
    "count": 5866,
    "percentage": 92.47989910137159
},
    "group2": {
    "name": "800 ms <= t < 1200 ms",
    "htmlName": "t >= 800 ms <br> t < 1200 ms",
    "count": 283,
    "percentage": 4.46161122497241
},
    "group3": {
    "name": "t >= 1200 ms",
    "htmlName": "t >= 1200 ms",
    "count": 194,
    "percentage": 3.0584896736559988
},
    "group4": {
    "name": "failed",
    "htmlName": "failed",
    "count": 0,
    "percentage": 0.0
},
    "meanNumberOfRequestsPerSecond": {
        "total": "103.98",
        "ok": "103.98",
        "ko": "-"
    }
}
    },"req_move-task-to-fi--1453605747": {
        type: "REQUEST",
        name: "Move task to first priority",
path: "Task lifecycle / Move task to first priority",
pathFormatted: "req_task-lifecycle---1328472469",
stats: {
    "name": "Move task to first priority",
    "numberOfRequests": {
        "total": "6343",
        "ok": "6343",
        "ko": "0"
    },
    "minResponseTime": {
        "total": "6",
        "ok": "6",
        "ko": "-"
    },
    "maxResponseTime": {
        "total": "3180",
        "ok": "3180",
        "ko": "-"
    },
    "meanResponseTime": {
        "total": "256",
        "ok": "256",
        "ko": "-"
    },
    "standardDeviation": {
        "total": "344",
        "ok": "344",
        "ko": "-"
    },
    "percentiles1": {
        "total": "98",
        "ok": "98",
        "ko": "-"
    },
    "percentiles2": {
        "total": "276",
        "ok": "276",
        "ko": "-"
    },
    "percentiles3": {
        "total": "1013",
        "ok": "1016",
        "ko": "-"
    },
    "percentiles4": {
        "total": "1866",
        "ok": "1808",
        "ko": "-"
    },
    "group1": {
    "name": "t < 800 ms",
    "htmlName": "t < 800 ms",
    "count": 5861,
    "percentage": 92.40107204792685
},
    "group2": {
    "name": "800 ms <= t < 1200 ms",
    "htmlName": "t >= 800 ms <br> t < 1200 ms",
    "count": 295,
    "percentage": 4.650796153239792
},
    "group3": {
    "name": "t >= 1200 ms",
    "htmlName": "t >= 1200 ms",
    "count": 187,
    "percentage": 2.9481317988333595
},
    "group4": {
    "name": "failed",
    "htmlName": "failed",
    "count": 0,
    "percentage": 0.0
},
    "meanNumberOfRequestsPerSecond": {
        "total": "103.98",
        "ok": "103.98",
        "ko": "-"
    }
}
    },"req_list-team-tasks--556250963": {
        type: "REQUEST",
        name: "List team tasks",
path: "Task lifecycle / List team tasks",
pathFormatted: "req_task-lifecycle---992278645",
stats: {
    "name": "List team tasks",
    "numberOfRequests": {
        "total": "6343",
        "ok": "6343",
        "ko": "0"
    },
    "minResponseTime": {
        "total": "2",
        "ok": "2",
        "ko": "-"
    },
    "maxResponseTime": {
        "total": "4884",
        "ok": "4884",
        "ko": "-"
    },
    "meanResponseTime": {
        "total": "201",
        "ok": "201",
        "ko": "-"
    },
    "standardDeviation": {
        "total": "346",
        "ok": "346",
        "ko": "-"
    },
    "percentiles1": {
        "total": "62",
        "ok": "62",
        "ko": "-"
    },
    "percentiles2": {
        "total": "208",
        "ok": "206",
        "ko": "-"
    },
    "percentiles3": {
        "total": "962",
        "ok": "1015",
        "ko": "-"
    },
    "percentiles4": {
        "total": "2514",
        "ok": "2933",
        "ko": "-"
    },
    "group1": {
    "name": "t < 800 ms",
    "htmlName": "t < 800 ms",
    "count": 5922,
    "percentage": 93.3627620999527
},
    "group2": {
    "name": "800 ms <= t < 1200 ms",
    "htmlName": "t >= 800 ms <br> t < 1200 ms",
    "count": 260,
    "percentage": 4.099006779126596
},
    "group3": {
    "name": "t >= 1200 ms",
    "htmlName": "t >= 1200 ms",
    "count": 161,
    "percentage": 2.5382311209207
},
    "group4": {
    "name": "failed",
    "htmlName": "failed",
    "count": 0,
    "percentage": 0.0
},
    "meanNumberOfRequestsPerSecond": {
        "total": "103.98",
        "ok": "103.98",
        "ko": "-"
    }
}
    },"req_delete-created--1296144370": {
        type: "REQUEST",
        name: "Delete created task",
path: "Task lifecycle / Delete created task",
pathFormatted: "req_task-lifecycle---470960176",
stats: {
    "name": "Delete created task",
    "numberOfRequests": {
        "total": "6343",
        "ok": "6343",
        "ko": "0"
    },
    "minResponseTime": {
        "total": "6",
        "ok": "6",
        "ko": "-"
    },
    "maxResponseTime": {
        "total": "4617",
        "ok": "4617",
        "ko": "-"
    },
    "meanResponseTime": {
        "total": "244",
        "ok": "244",
        "ko": "-"
    },
    "standardDeviation": {
        "total": "347",
        "ok": "347",
        "ko": "-"
    },
    "percentiles1": {
        "total": "93",
        "ok": "93",
        "ko": "-"
    },
    "percentiles2": {
        "total": "269",
        "ok": "269",
        "ko": "-"
    },
    "percentiles3": {
        "total": "984",
        "ok": "973",
        "ko": "-"
    },
    "percentiles4": {
        "total": "1865",
        "ok": "1943",
        "ko": "-"
    },
    "group1": {
    "name": "t < 800 ms",
    "htmlName": "t < 800 ms",
    "count": 5896,
    "percentage": 92.95286142204004
},
    "group2": {
    "name": "800 ms <= t < 1200 ms",
    "htmlName": "t >= 800 ms <br> t < 1200 ms",
    "count": 270,
    "percentage": 4.256660886016081
},
    "group3": {
    "name": "t >= 1200 ms",
    "htmlName": "t >= 1200 ms",
    "count": 177,
    "percentage": 2.790477691943875
},
    "group4": {
    "name": "failed",
    "htmlName": "failed",
    "count": 0,
    "percentage": 0.0
},
    "meanNumberOfRequestsPerSecond": {
        "total": "103.98",
        "ok": "103.98",
        "ko": "-"
    }
}
    }
}

     }
}

}

function fillStats(stat){
    $("#numberOfRequests").append(stat.numberOfRequests.total);
    $("#numberOfRequestsOK").append(stat.numberOfRequests.ok);
    $("#numberOfRequestsKO").append(stat.numberOfRequests.ko);

    $("#minResponseTime").append(stat.minResponseTime.total);
    $("#minResponseTimeOK").append(stat.minResponseTime.ok);
    $("#minResponseTimeKO").append(stat.minResponseTime.ko);

    $("#maxResponseTime").append(stat.maxResponseTime.total);
    $("#maxResponseTimeOK").append(stat.maxResponseTime.ok);
    $("#maxResponseTimeKO").append(stat.maxResponseTime.ko);

    $("#meanResponseTime").append(stat.meanResponseTime.total);
    $("#meanResponseTimeOK").append(stat.meanResponseTime.ok);
    $("#meanResponseTimeKO").append(stat.meanResponseTime.ko);

    $("#standardDeviation").append(stat.standardDeviation.total);
    $("#standardDeviationOK").append(stat.standardDeviation.ok);
    $("#standardDeviationKO").append(stat.standardDeviation.ko);

    $("#percentiles1").append(stat.percentiles1.total);
    $("#percentiles1OK").append(stat.percentiles1.ok);
    $("#percentiles1KO").append(stat.percentiles1.ko);

    $("#percentiles2").append(stat.percentiles2.total);
    $("#percentiles2OK").append(stat.percentiles2.ok);
    $("#percentiles2KO").append(stat.percentiles2.ko);

    $("#percentiles3").append(stat.percentiles3.total);
    $("#percentiles3OK").append(stat.percentiles3.ok);
    $("#percentiles3KO").append(stat.percentiles3.ko);

    $("#percentiles4").append(stat.percentiles4.total);
    $("#percentiles4OK").append(stat.percentiles4.ok);
    $("#percentiles4KO").append(stat.percentiles4.ko);

    $("#meanNumberOfRequestsPerSecond").append(stat.meanNumberOfRequestsPerSecond.total);
    $("#meanNumberOfRequestsPerSecondOK").append(stat.meanNumberOfRequestsPerSecond.ok);
    $("#meanNumberOfRequestsPerSecondKO").append(stat.meanNumberOfRequestsPerSecond.ko);
}
