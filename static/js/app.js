$('a#process_input').click(function() {
    $.getJSON('/display', {
      line: $( "#lineform" ).val(),
      stop: $( "#stopform" ).val()
    }, function(result) {
        $("div#trainfeed").prepend(result.data);
      });
});

/////////////////////////////////////////////////////////////////

var map = L.eeGeo.map('map', eeGeo_api_key, {
  center: [40.7128,-74.0060],
  zoom: 15
});
var my_icon = L.icon({
  iconUrl: '/static/js/black_map_marker.png',
  iconSize: [15, 15],
});

d3.csv("/static/js/subway_stops.csv").then(function(stops_info) {
  stops_info.forEach(function(data2) {
    data2.lat = +data2.lat;
    data2.lon = +data2.lon;
  })
  stops_info.forEach(function(data2) {
    L.marker([data2.lat,data2.lon],{icon: my_icon})
    .bindPopup(`<p><strong> ${data2.NAME} <br /><hr></strong> ${data2.LINE} </p>`).addTo(map);
    });
    
  setTimeout(function() {
    map.setView([40.7128,-74.0060], 17, {headingDegrees: 204.374, tiltDegrees:15.0});
  }, 10000);

// ONE TWO THREE
L.polyline(one_train, {color:'red', opacity: .75}).addTo(map);
L.polyline(Two_train, {color:'red' ,opacity: .75}).addTo(map);
L.polyline(Three_train, {color:'red' ,opacity: .75}).addTo(map);

// FOUR FIVE SIX
L.polyline(Four_train, {color:'green', opacity: .75}).addTo(map);
L.polyline(Five_train, {color:'green', opacity: 1}).addTo(map);
L.polyline(Five_Point_5_train, {color:'green', opacity: 1}).addTo(map);
L.polyline(Six_train, {color:'green', opacity: .75}).addTo(map);

// SEVEN
L.polyline(Seven_train, {color:'purple', opacity: .75}).addTo(map);

// ACE 
L.polyline(A_train, {color:'blue', opacity: .75}).addTo(map);
L.polyline(A_A_train, {color:'blue', opacity: .75}).addTo(map);
L.polyline(C_train, {color:'blue', opacity: .75}).addTo(map);
L.polyline(E_train, {color:'blue', opacity: 1}).addTo(map);

// BDFM
L.polyline(B_train, {color:'#FF8333', opacity: .85}).addTo(map);
L.polyline(D_train, {color:'#FF8333', opacity: .85}).addTo(map);
L.polyline(F_train, {color:'#FF8333', opacity: .85}).addTo(map);
L.polyline(M_train, {color:'#FF8333', opacity: .85}).addTo(map);

// JZ
L.polyline(J_train, {color:'#3B250A', opacity: .85}).addTo(map);
L.polyline(Z_train, {color:'#3B250A', opacity: .85}).addTo(map);

// G
L.polyline(G_train, {color:'#46FF33', opacity: .85}).addTo(map);

// L 
L.polyline(L_train, {color:'black', opacity: .7}).addTo(map);

// S
L.polyline(S_train, {color:'black', opacity: .7}).addTo(map);

// NQRW
L.polyline(N_train, {color:'yellow', opacity: .75 }).addTo(map);
L.polyline(Q_train, {color:'yellow', opacity: .75 }).addTo(map);
L.polyline(R_train, {color:'yellow', opacity: .75 }).addTo(map);
L.polyline(W_train, {color:'yellow', opacity: .75 }).attTo(map);
});

/////////////////////////////////////////////////////////////////


var svgWidth = 880;
var svgHeight = 680;

// Define the chart's margins as an object
var chartMargin = {
  top: 40,
  right: 40,
  bottom: 40,
  left: 40
};

// Define dimensions of the chart area
var chartWidth = svgWidth - chartMargin.left - chartMargin.right;
var chartHeight = svgHeight - chartMargin.top - chartMargin.bottom;

// Select body, append SVG area to it, and set the dimensions
var svg = d3.select("#delays")
  .append("svg")
  .attr("viewbox", "0 0 100 75")
  .attr("preserveAspectRatio", "none")
  .attr("height", svgHeight)
  .attr("width", svgWidth);

// Append a group to the SVG area and shift ('translate') it to the right and to the bottom
var chartGroup = svg.append("g")
  .attr("transform", `translate(${chartMargin.left}, ${chartMargin.top})`);

d3.json("/api/delays").then(function(delayData) {
  var yScale = d3.scaleBand()
    .domain(delayData.map(d => d.line))
    .range([0, chartHeight])
    .padding(0.1);

  // Create a linear scale for the vertical axis.
  var xScale = d3.scaleLinear()
    .domain([d3.max(delayData, d => (d.count/60)), 0])
    .range([chartWidth, 0]);
  
  var xAxisScale = d3.scaleLinear()
    .domain([d3.min(delayData, d => (d.count/60)), d3.max(delayData, d => (d.count/60))])
    .range([0, chartWidth]);

  var bottomAxis = d3.axisBottom(xAxisScale).ticks(15);
  var leftAxis = d3.axisLeft(yScale).tickSize(0);

  var toolTip = d3.tip()
    .attr("class", "tooltip")
    .offset([0, 10])
    .html(function(d) {
      return (`<strong>${d.line} Line<strong>: ${Math.round(d.count/60)} minutes`);
    }
  );

  svg.call(toolTip);

  chartGroup.selectAll(".bar")
    .data(delayData)
    .enter()
    .append("rect")
    .attr("class", "bar")
    .attr("x", d => xAxisScale(Math.min(0, (d.count/60))))
    .attr("y", d => yScale(d.line))
    .attr("fill", d => d.color)
    .attr("width", d => Math.abs(xAxisScale(d.count/60) - xAxisScale(0)))
    .attr("height", yScale.bandwidth())
    .attr("opacity", ".75")
    .on('mouseover', toolTip.show)
    .on('mouseout', toolTip.hide);
  
  chartGroup.append("g")
    .attr("transform", `translate(${xAxisScale(0)}, 0)`)
    .call(leftAxis);

  chartGroup.append("g")
    .attr("transform", `translate(0, ${chartHeight})`)
    .call(bottomAxis);
});

setTimeout(function () {
  $( "#loading" ).remove();
}, 11000);