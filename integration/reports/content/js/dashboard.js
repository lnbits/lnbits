/*
   Licensed to the Apache Software Foundation (ASF) under one or more
   contributor license agreements.  See the NOTICE file distributed with
   this work for additional information regarding copyright ownership.
   The ASF licenses this file to You under the Apache License, Version 2.0
   (the "License"); you may not use this file except in compliance with
   the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/
var showControllersOnly = false;
var seriesFilter = "";
var filtersOnlySampleSeries = true;

/*
 * Add header in statistics table to group metrics by category
 * format
 *
 */
function summaryTableHeader(header) {
    var newRow = header.insertRow(-1);
    newRow.className = "tablesorter-no-sort";
    var cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Requests";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 3;
    cell.innerHTML = "Executions";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 7;
    cell.innerHTML = "Response Times (ms)";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Throughput";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 2;
    cell.innerHTML = "Network (KB/sec)";
    newRow.appendChild(cell);
}

/*
 * Populates the table identified by id parameter with the specified data and
 * format
 *
 */
function createTable(table, info, formatter, defaultSorts, seriesIndex, headerCreator) {
    var tableRef = table[0];

    // Create header and populate it with data.titles array
    var header = tableRef.createTHead();

    // Call callback is available
    if(headerCreator) {
        headerCreator(header);
    }

    var newRow = header.insertRow(-1);
    for (var index = 0; index < info.titles.length; index++) {
        var cell = document.createElement('th');
        cell.innerHTML = info.titles[index];
        newRow.appendChild(cell);
    }

    var tBody;

    // Create overall body if defined
    if(info.overall){
        tBody = document.createElement('tbody');
        tBody.className = "tablesorter-no-sort";
        tableRef.appendChild(tBody);
        var newRow = tBody.insertRow(-1);
        var data = info.overall.data;
        for(var index=0;index < data.length; index++){
            var cell = newRow.insertCell(-1);
            cell.innerHTML = formatter ? formatter(index, data[index]): data[index];
        }
    }

    // Create regular body
    tBody = document.createElement('tbody');
    tableRef.appendChild(tBody);

    var regexp;
    if(seriesFilter) {
        regexp = new RegExp(seriesFilter, 'i');
    }
    // Populate body with data.items array
    for(var index=0; index < info.items.length; index++){
        var item = info.items[index];
        if((!regexp || filtersOnlySampleSeries && !info.supportsControllersDiscrimination || regexp.test(item.data[seriesIndex]))
                &&
                (!showControllersOnly || !info.supportsControllersDiscrimination || item.isController)){
            if(item.data.length > 0) {
                var newRow = tBody.insertRow(-1);
                for(var col=0; col < item.data.length; col++){
                    var cell = newRow.insertCell(-1);
                    cell.innerHTML = formatter ? formatter(col, item.data[col]) : item.data[col];
                }
            }
        }
    }

    // Add support of columns sort
    table.tablesorter({sortList : defaultSorts});
}

$(document).ready(function() {

    // Customize table sorter default options
    $.extend( $.tablesorter.defaults, {
        theme: 'blue',
        cssInfoBlock: "tablesorter-no-sort",
        widthFixed: true,
        widgets: ['zebra']
    });

    var data = {"OkPercent": 94.44444444444444, "KoPercent": 5.555555555555555};
    var dataset = [
        {
            "label" : "FAIL",
            "data" : data.KoPercent,
            "color" : "#FF6347"
        },
        {
            "label" : "PASS",
            "data" : data.OkPercent,
            "color" : "#9ACD32"
        }];
    $.plot($("#flot-requests-summary"), dataset, {
        series : {
            pie : {
                show : true,
                radius : 1,
                label : {
                    show : true,
                    radius : 3 / 4,
                    formatter : function(label, series) {
                        return '<div style="font-size:8pt;text-align:center;padding:2px;color:white;">'
                            + label
                            + '<br/>'
                            + Math.round10(series.percent, -2)
                            + '%</div>';
                    },
                    background : {
                        opacity : 0.5,
                        color : '#000'
                    }
                }
            }
        },
        legend : {
            show : true
        }
    });

    // Creates APDEX table
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.7727272727272727, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [1.0, 500, 1500, "[wallet] Get wallet balance"], "isController": false}, {"data": [1.0, 500, 1500, "TPoS Create"], "isController": true}, {"data": [1.0, 500, 1500, "[wallet] Get currencies"], "isController": false}, {"data": [1.0, 500, 1500, "[tpos ]Go to \"tpos\" page"], "isController": false}, {"data": [0.5, 500, 1500, "[tpos] Get exchange rates"], "isController": false}, {"data": [0.5, 500, 1500, "[tpos] Create payment"], "isController": false}, {"data": [1.0, 500, 1500, "[wallet] Get payments"], "isController": false}, {"data": [1.0, 500, 1500, "[tpos] Update tpos (add tips)"], "isController": false}, {"data": [1.0, 500, 1500, "[wallet] Go to wallet page"], "isController": false}, {"data": [1.0, 500, 1500, "[tpos] Check payment"], "isController": false}, {"data": [1.0, 500, 1500, "[wallet] Get main page"], "isController": false}, {"data": [0.5, 500, 1500, "Init Wallet"], "isController": true}, {"data": [0.0, 500, 1500, "[tpos] Enable \"tpos\""], "isController": false}, {"data": [1.0, 500, 1500, "[tpos] Go to TPOS page"], "isController": false}, {"data": [0.0, 500, 1500, "[wallet] Pay Invoice"], "isController": false}, {"data": [1.0, 500, 1500, "[wallet] Create tips wallet"], "isController": false}, {"data": [1.0, 500, 1500, "[wallet] Create new wallet"], "isController": false}, {"data": [1.0, 500, 1500, "[tpos ]Get tpos "], "isController": false}, {"data": [1.0, 500, 1500, "[tpos] Create tpos"], "isController": false}, {"data": [0.0, 500, 1500, "TPoS Extension"], "isController": true}, {"data": [1.0, 500, 1500, "[tpos] Create tpos (atm)"], "isController": false}, {"data": [0.5, 500, 1500, "TPoS Page"], "isController": true}]}, function(index, item){
        switch(index){
            case 0:
                item = item.toFixed(3);
                break;
            case 1:
            case 2:
                item = formatDuration(item);
                break;
        }
        return item;
    }, [[0, 0]], 3);

    // Create statistics table
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 18, 1, 5.555555555555555, 330.1666666666667, 15, 2345, 71.0, 1118.300000000002, 2345.0, 2345.0, 1.6984336667295716, 4.732983227967541, 0.0], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["[wallet] Get wallet balance", 1, 0, 0.0, 33.0, 33, 33, 33.0, 33.0, 33.0, 33.0, 30.303030303030305, 4.438920454545454, 0.0], "isController": false}, {"data": ["TPoS Create", 1, 0, 0.0, 170.0, 170, 170, 170.0, 170.0, 170.0, 170.0, 5.88235294117647, 7.261029411764706, 0.0], "isController": true}, {"data": ["[wallet] Get currencies", 1, 0, 0.0, 15.0, 15, 15, 15.0, 15.0, 15.0, 15.0, 66.66666666666667, 72.72135416666667, 0.0], "isController": false}, {"data": ["[tpos ]Go to \"tpos\" page", 1, 0, 0.0, 184.0, 184, 184, 184.0, 184.0, 184.0, 184.0, 5.434782608695652, 57.081139605978265, 0.0], "isController": false}, {"data": ["[tpos] Get exchange rates", 1, 0, 0.0, 884.0, 884, 884, 884.0, 884.0, 884.0, 884.0, 1.1312217194570138, 0.16570630656108598, 0.0], "isController": false}, {"data": ["[tpos] Create payment", 1, 0, 0.0, 982.0, 982, 982, 982.0, 982.0, 982.0, 982.0, 1.0183299389002036, 0.6344672861507128, 0.0], "isController": false}, {"data": ["[wallet] Get payments", 1, 0, 0.0, 53.0, 53, 53, 53.0, 53.0, 53.0, 53.0, 18.867924528301884, 2.3216391509433962, 0.0], "isController": false}, {"data": ["[tpos] Update tpos (add tips)", 1, 0, 0.0, 71.0, 71, 71, 71.0, 71.0, 71.0, 71.0, 14.084507042253522, 6.03818221830986, 0.0], "isController": false}, {"data": ["[wallet] Go to wallet page", 1, 0, 0.0, 245.0, 245, 245, 245.0, 245.0, 245.0, 245.0, 4.081632653061225, 38.2453762755102, 0.0], "isController": false}, {"data": ["[tpos] Check payment", 1, 0, 0.0, 435.0, 435, 435, 435.0, 435.0, 435.0, 435.0, 2.2988505747126435, 0.4871587643678161, 0.0], "isController": false}, {"data": ["[wallet] Get main page", 1, 0, 0.0, 227.0, 227, 227, 227.0, 227.0, 227.0, 227.0, 4.405286343612335, 15.237816629955947, 0.0], "isController": false}, {"data": ["Init Wallet", 1, 0, 0.0, 684.0, 684, 684, 684.0, 684.0, 684.0, 684.0, 1.461988304093567, 21.864149305555554, 0.0], "isController": true}, {"data": ["[tpos] Enable \"tpos\"", 1, 0, 0.0, 2345.0, 2345, 2345, 2345.0, 2345.0, 2345.0, 2345.0, 0.42643923240938164, 5.535381130063965, 0.0], "isController": false}, {"data": ["[tpos] Go to TPOS page", 1, 0, 0.0, 152.0, 152, 152, 152.0, 152.0, 152.0, 152.0, 6.578947368421052, 60.4505037006579, 0.0], "isController": false}, {"data": ["[wallet] Pay Invoice", 1, 1, 100.0, 36.0, 36, 36, 36.0, 36.0, 36.0, 36.0, 27.777777777777775, 5.398220486111112, 0.0], "isController": false}, {"data": ["[wallet] Create tips wallet", 1, 0, 0.0, 41.0, 41, 41, 41.0, 41.0, 41.0, 41.0, 24.390243902439025, 9.360708841463413, 0.0], "isController": false}, {"data": ["[wallet] Create new wallet", 1, 0, 0.0, 70.0, 70, 70, 70.0, 70.0, 70.0, 70.0, 14.285714285714285, 5.454799107142857, 0.0], "isController": false}, {"data": ["[tpos ]Get tpos ", 1, 0, 0.0, 71.0, 71, 71, 71.0, 71.0, 71.0, 71.0, 14.084507042253522, 1.733054577464789, 0.0], "isController": false}, {"data": ["[tpos] Create tpos", 1, 0, 0.0, 54.0, 54, 54, 54.0, 54.0, 54.0, 54.0, 18.51851851851852, 7.414641203703704, 0.0], "isController": false}, {"data": ["TPoS Extension", 1, 0, 0.0, 2600.0, 2600, 2600, 2600.0, 2600.0, 2600.0, 2600.0, 0.38461538461538464, 9.07940204326923, 0.0], "isController": true}, {"data": ["[tpos] Create tpos (atm)", 1, 0, 0.0, 45.0, 45, 45, 45.0, 45.0, 45.0, 45.0, 22.22222222222222, 9.00607638888889, 0.0], "isController": false}, {"data": ["TPoS Page", 1, 0, 0.0, 1036.0, 1036, 1036, 1036.0, 1036.0, 1036.0, 1036.0, 0.9652509652509653, 9.010580055501931, 0.0], "isController": true}]}, function(index, item){
        switch(index){
            // Errors pct
            case 3:
                item = item.toFixed(2) + '%';
                break;
            // Mean
            case 4:
            // Mean
            case 7:
            // Median
            case 8:
            // Percentile 1
            case 9:
            // Percentile 2
            case 10:
            // Percentile 3
            case 11:
            // Throughput
            case 12:
            // Kbytes/s
            case 13:
            // Sent Kbytes/s
                item = item.toFixed(2);
                break;
        }
        return item;
    }, [[0, 0]], 0, summaryTableHeader);

    // Create error table
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["404/Not Found", 1, 100.0, 5.555555555555555], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 18, 1, "404/Not Found", 1, "", "", "", "", "", "", "", ""], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["[wallet] Pay Invoice", 1, 1, "404/Not Found", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
