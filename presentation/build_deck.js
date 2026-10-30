// Builds citibike-presentation.pptx: 16 slides for the 15-minute talk, then backups for the Q&A.
// Figures come from img/ (the report figures without their titles, made by crop_figures.py).
// Run: NODE_PATH=<folder with pptxgenjs, react, react-dom, react-icons, sharp> node build_deck.js <apply_theme.js>

const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require(process.argv[2]);

const IMG = path.join(__dirname, "img");
const OUT = path.join(__dirname, "citibike-presentation.pptx");

// the report figures' palette, so slides and charts read as one
const THEME = {
  name: "Citi Bike rebalancing",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "22252A", // ink
    lt1: "FFFFFF",
    dk2: "15233B", // night navy, title and closing slides
    lt2: "F3F1EC", // warm grey card
    accent1: "3B7DD8", // blue: recommended, stations gaining bikes
    accent2: "D4692A", // orange
    accent3: "C9403A", // red: stations losing bikes, riders turned away
    accent4: "1F4F99", // dark blue
    accent5: "9A978F", // context grey
    accent6: "6B6E75", // muted text
    hlink: "3B7DD8",
    folHlink: "1F4F99",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Citi Bike rebalancing";
pres.author = "Team Jupyter";
const C = pres.SchemeColor;

const W = 13.333;
const M = 0.6; // side margin
const CONTENT_TOP = 1.45;

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    {
      placeholder: {
        options: {
          name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.95,
          fontSize: 28, bold: true, color: C.text1, valign: "top", align: "left", margin: 0,
        },
        text: "",
      },
    },
    {
      text: {
        text: "Team Jupyter  |  Citi Bike rebalancing",
        options: { x: M, y: 7.05, w: 6, h: 0.3, fontSize: 10, color: C.accent6, margin: 0 },
      },
    },
  ],
  slideNumber: { x: W - M - 0.5, y: 7.05, w: 0.5, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
});

pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text2 },
  objects: [
    {
      placeholder: {
        options: {
          name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.95,
          fontSize: 28, bold: true, color: C.background1, valign: "top", align: "left", margin: 0,
        },
        text: "",
      },
    },
  ],
});

async function icon(Icon, hex) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Icon, { color: "#" + hex, size: 256 }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

// places a figure inside the box at its own aspect ratio, centred, and returns where it landed
async function figure(slide, file, box, name) {
  const meta = await sharp(path.join(IMG, file)).metadata();
  const scale = Math.min(box.w / meta.width, box.h / meta.height);
  const w = meta.width * scale;
  const h = meta.height * scale;
  const x = box.x + (box.w - w) / 2;
  const y = box.y + (box.h - h) / 2;
  slide.addImage({ path: path.join(IMG, file), x, y, w, h, objectName: name, altText: name });
  return { x, y, w, h };
}

function caption(slide, text, x, y, w) {
  slide.addText(text, { x, y, w, h: 0.35, fontSize: 11, color: C.accent6, margin: 0, isTextBox: true, objectName: "caption" });
}

// a big number with a short label under it
function stat(slide, value, label, x, y, w, color = C.accent1, size = 40) {
  slide.addText(value, {
    x, y, w, h: size / 60, fontSize: size, bold: true, color, margin: 0, valign: "bottom", isTextBox: true, objectName: "stat " + value,
  });
  slide.addText(label, {
    x, y: y + size / 60 + 0.05, w, h: 0.75, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "stat label",
  });
}

function card(slide, x, y, w, h, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { type: "none" }, rectRadius: 0.08, objectName: "card" });
}

function content(section, title) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  slide.addText(title, { placeholder: "title" });
  return slide;
}

async function build() {
  const truckIcon = await icon(fa.FaTruck, HEX.accent1);
  const bikeIcon = await icon(fa.FaBicycle, HEX.accent1);
  const valetIcon = await icon(fa.FaUserCheck, HEX.accent1);
  const starIcon = await icon(fa.FaStar, HEX.accent1);

  // ---------- 1. Title ----------
  pres.addSection({ title: "Problem" });
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Problem" });
    s.addText("DAO2702X  |  TEAM JUPYTER", { x: M, y: 1.2, w: 7, h: 0.4, fontSize: 14, bold: true, color: C.accent5, charSpacing: 3, margin: 0, isTextBox: true });
    s.addText("Where Citi Bike\nshould move\nits bikes", { x: M, y: 1.75, w: 7, h: 2.7, fontSize: 48, bold: true, color: C.background1, margin: 0, valign: "top", isTextBox: true });
    s.addText("Six schedules replayed on a year of real trips", {
      x: M, y: 4.85, w: 6.3, h: 1.0, fontSize: 20, color: "C9D3E3", margin: 0, valign: "top", isTextBox: true,
    });
    const statBox = (y, value, label) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.3, y, w: 4.4, h: 1.85, fill: { color: "22344F" }, line: { type: "none" }, rectRadius: 0.08 });
      s.addText(value, { x: 8.6, y: y + 0.2, w: 4, h: 0.9, fontSize: 54, bold: true, color: "6FA3EA", margin: 0, isTextBox: true });
      s.addText(label, { x: 8.6, y: y + 1.1, w: 4, h: 0.6, fontSize: 16, color: C.background1, margin: 0, isTextBox: true });
    };
    statBox(1.6, "62%", "fewer riders turned away");
    statBox(3.75, "57%", "fewer bikes moved");
    s.addText("compared with a half-full reset every night", { x: 8.3, y: 5.75, w: 4.4, h: 0.5, fontSize: 13, color: "C9D3E3", margin: 0, isTextBox: true });
    s.addNotes("SPEAKER 1 (slides 1 to 3, about 2:30)\n\nStart with the result. Our schedule turns away 62% fewer riders than resetting every station to half full each night, and it moves 57% fewer bikes.\nWe got there by replaying every Citi Bike trip from October 2024 to September 2026. The next 15 minutes show how.\n\nIf you want an opening line: at 8:45 a commuter walks up to an empty station and leaves. We want fewer of those for every bike Citi Bike pays to move.");
  }

  // ---------- 2. The imbalance ----------
  {
    const s = content("Problem", "Every workday morning, bikes flow from homes to offices");
    const f = await figure(s, "fig2-rush-map.png", { x: M, y: CONTENT_TOP, w: 7.9, h: 5.15 }, "rush map");
    caption(s, "Bikes each station gains over a workday rush; red loses, blue gains. Development year.", M, f.y + f.h + 0.05, 7.9);
    const x = 9.0;
    stat(s, "9,400", "trips start in the 08:00 hour of a workday", x, 1.6, 3.7);
    stat(s, "1,055", "bikes leave Brooklyn each morning rush, while Manhattan gains 935", x, 3.15, 3.7, C.accent3);
    s.addText("So home stations run out of bikes and office stations run out of docks. In the evening it flips.", {
      x, y: 4.75, w: 3.7, h: 1.3, fontSize: 16, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("The maps show the morning and the evening rush. Red stations lose bikes, blue ones gain them.\n9,400 trips start in the 08:00 hour alone. In the morning rush 417 stations lose 5 bikes or more and 294 gain 5 or more. Brooklyn loses 1,055 bikes and Manhattan gains 935. In the evening it flips, and Manhattan loses 1,263.\nThe next rider at a red station finds no bike. At a blue one they find no free dock. Either way the trip is lost.\n\nIf asked why the Bronx and Jersey City are grey: their flows are small and even out, so they need little work.");
  }

  // ---------- 3. Today and the question ----------
  {
    const s = content("Problem", "Citi Bike moves 2,500 bikes a day, but its plan is not public");
    const tools = [
      [truckIcon, "Vans and box trucks", "bulk moves over longer distances, around the clock"],
      [bikeIcon, "Bike trains", "e-bikes towing 12 to 16 bikes on narrow streets"],
      [valetIcon, "Valets", "staff at the busiest stations take bikes beyond the docks"],
      [starIcon, "Bike Angels", "members earn points for riding from full to empty stations"],
    ];
    s.addText("How Citi Bike rebalances today", { x: M, y: CONTENT_TOP + 0.05, w: 5.6, h: 0.4, fontSize: 16, bold: true, color: C.accent6, margin: 0, isTextBox: true });
    tools.forEach(([img, head, body], i) => {
      const y = CONTENT_TOP + 0.65 + i * 1.18;
      s.addShape(pres.shapes.OVAL, { x: M, y, w: 0.8, h: 0.8, fill: { color: "E3ECF8" }, line: { type: "none" } });
      s.addImage({ data: img, x: M + 0.2, y: y + 0.2, w: 0.4, h: 0.4 });
      s.addText(head, { x: M + 1.05, y: y - 0.02, w: 4.6, h: 0.4, fontSize: 17, bold: true, color: C.text1, margin: 0, isTextBox: true });
      s.addText(body, { x: M + 1.05, y: y + 0.38, w: 4.6, h: 0.5, fontSize: 14, color: C.accent6, margin: 0, valign: "top", isTextBox: true });
    });
    const x = 7.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: CONTENT_TOP + 0.05, w: 5.73, h: 3.3, fill: { color: C.text2 }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText("OUR QUESTION", { x: x + 0.35, y: CONTENT_TOP + 0.3, w: 5, h: 0.35, fontSize: 13, bold: true, color: "6FA3EA", charSpacing: 2, margin: 0, isTextBox: true });
    s.addText("Each night, which stations should Citi Bike restock or clear, and by how many bikes, to turn away the fewest riders for each bike it moves?\n\nAnd is a second visit during the day worth it?", {
      x: x + 0.35, y: CONTENT_TOP + 0.75, w: 5.0, h: 2.45, fontSize: 18, color: C.background1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addText("Its monthly reports give bikes moved, but no targets or shortages. We compare with two simple rules instead:", {
      x, y: CONTENT_TOP + 3.6, w: 5.73, h: 0.7, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    [["Never move a bike", 0], ["Reset every station to half full each night", 1]].forEach(([t, i]) => {
      card(s, x + i * 2.5, CONTENT_TOP + 4.45, i ? 3.23 : 2.3, 0.85);
      s.addText(t, { x: x + i * 2.5 + 0.2, y: CONTENT_TOP + 4.45, w: (i ? 3.23 : 2.3) - 0.4, h: 0.85, fontSize: 14, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
    });
    s.addNotes("Citi Bike already works on this. It has trucks and vans, e-bikes towing trailers of bikes, valets at the busiest stations, and Bike Angels, which pays members in points to ride bikes from full stations to empty ones. It tells NYC DOT it moves about 2,500 bikes a day.\nIt doesn't publish which stations it fills, to what level, or how many riders still find a station empty. So we can't score its plan directly.\nRead the question out. We compare against never moving a bike and against a half-full reset, and we check our workload against the moves Citi Bike reports.\n\nIf asked whether half full is what Citi Bike does: we don't know, its method isn't public. Half full is a simple rule we use as a yardstick.");
  }

  // ---------- 4. Method ----------
  pres.addSection({ title: "Data and method" });
  {
    const s = content("Data and method", "We replay 92 million real trips through any schedule");
    const steps = [
      ["92.1M trips", "every Citi Bike trip, Oct 2024 to Sep 2026, with start and end station and time"],
      ["Stock every 5 min", "bikes in each of 2,470 stations rebuilt from trips leaving and arriving"],
      ["Replay a schedule", "set each station's level at 04:00, then replay the real riders"],
      ["Count the losses", "riders turned away at an empty or full station, and bikes moved"],
    ];
    const bw = 2.7, gap = 0.4, y = CONTENT_TOP + 0.1;
    steps.forEach(([head, body], i) => {
      const x = M + i * (bw + gap);
      card(s, x, y, bw, 2.2, i === 3 ? "E3ECF8" : C.background2);
      s.addText(head, { x: x + 0.2, y: y + 0.2, w: bw - 0.4, h: 0.5, fontSize: 19, bold: true, color: i === 3 ? C.accent4 : C.text1, margin: 0, isTextBox: true });
      s.addText(body, { x: x + 0.2, y: y + 0.75, w: bw - 0.4, h: 1.35, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true });
      if (i < 3) s.addShape(pres.shapes.CHEVRON, { x: x + bw + 0.1, y: y + 0.9, w: 0.2, h: 0.4, fill: { color: C.accent5 }, line: { type: "none" } });
    });
    // split by time
    const ty = 4.2;
    s.addText("The first year picks the settings, the second year scores them", { x: M, y: ty, w: 12, h: 0.4, fontSize: 16, bold: true, color: C.accent6, margin: 0, isTextBox: true });
    const half = (W - 2 * M - 0.2) / 2;
    s.addShape(pres.shapes.RECTANGLE, { x: M, y: ty + 0.55, w: half, h: 0.9, fill: { color: C.accent5 }, line: { type: "none" } });
    s.addShape(pres.shapes.RECTANGLE, { x: M + half + 0.2, y: ty + 0.55, w: half, h: 0.9, fill: { color: C.accent1 }, line: { type: "none" } });
    s.addText([{ text: "Development year  ", options: { bold: true } }, { text: "Oct 2024 to Sep 2025: explore and pick settings" }], {
      x: M + 0.2, y: ty + 0.55, w: half - 0.4, h: 0.9, fontSize: 15, color: C.background1, margin: 0, valign: "middle", isTextBox: true,
    });
    s.addText([{ text: "Test year  ", options: { bold: true } }, { text: "Oct 2025 to Sep 2026: used once, to score" }], {
      x: M + half + 0.4, y: ty + 0.55, w: half - 0.4, h: 0.9, fontSize: 15, color: C.background1, margin: 0, valign: "middle", isTextBox: true,
    });
    s.addText("A rider turned away at an empty station never rides. The bike they would have brought never arrives, and the station at the other end can run short too.", {
      x: M, y: ty + 1.7, w: 12.1, h: 0.7, fontSize: 15, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("SPEAKER 2 (slides 4 and 5, about 2:30)\n\nThe trip data never says how many bikes are in a station. We work it out: start from a level, add the bikes that arrive and take away the ones that leave, every 5 minutes, for 2,470 stations.\nThat gives us a simulator. A schedule sets every station's level at 04:00, the quietest hour, and then we replay the real riders. If a rider reaches an empty or full station, they are turned away and we count them.\nWe fixed a few problems in the raw files first. Some months write station 7293.10 as 7293.1. Depots and demo units show up as stations. One file repeats 512 trips. And on 23 February 2026 the system shut for 22 cm of snow. After the fixes, 99.9% of trips start at a public station.\nThe first year is for exploring and picking settings. The second year we used once, to score.\n\nIf asked why a lost rider matters further down the line: if they never ride, the bike they would have dropped off never arrives, so the next station runs short too. A simpler model that skips this makes never rebalancing look far better than it is: 2,173 riders turned away a day instead of 18,189.");
  }

  // ---------- 5. Clock ----------
  {
    const s = content("Data and method", "Homes empty before 10:00, offices empty after 16:00");
    const f = await figure(s, "fig3-neighbourhood-clock.png", { x: M, y: CONTENT_TOP, w: 8.6, h: 5.15 }, "neighbourhood clock");
    caption(s, "Bikes gained per workday hour, 24 neighbourhoods with the largest swings. Development year.", M, f.y + f.h + 0.05, 8.6);
    const x = 9.6;
    stat(s, "726", "bikes leave the East Village over the morning rush", x, 1.6, 3.1, C.accent3);
    stat(s, "1,119", "arrive in Midtown and Times Square over the same hours", x, 3.1, 3.1);
    s.addText("Offices empty fast between 16:00 and 19:00. A visit at 14:00 still has time to help.", {
      x, y: 4.65, w: 3.1, h: 1.6, fontSize: 15, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("Each row is a neighbourhood and each column an hour of a workday. Red means losing bikes, blue gaining.\nThe homes at the top empty between 06:00 and 10:00. The East Village alone loses 726 bikes. The offices at the bottom fill over the same hours, and Midtown and Times Square gain 1,119. In the evening it goes the other way.\nTwo things matter for the plan. Williamsburg and the West Village lose bikes again after 21:00, from nightlife. And the office districts empty fast between 16:00 and 19:00, so a visit at 14:00 still has time to help.\n\nHand over with: the pattern is strong, but can you plan it the night before?");
  }

  // ---------- 6. Predictable ----------
  pres.addSection({ title: "Analysis" });
  {
    const s = content("Analysis", "Tomorrow looks like the last ten days, so plan it the night before");
    const colW = (W - 2 * M - 0.5) / 2;
    const panels = [
      ["0.998", "a station's morning flow, odd weeks against even weeks", "fig4-habit.png"],
      ["0.90", "one day against the average of its last 10 workdays", "fig5-single-day.png"],
    ];
    for (const [i, [value, label, file]] of panels.entries()) {
      const x = M + i * (colW + 0.5);
      s.addText(value, { x, y: CONTENT_TOP, w: 1.9, h: 0.75, fontSize: 40, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(label, { x: x + 2.0, y: CONTENT_TOP, w: colW - 2.0, h: 0.75, fontSize: 15, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
      await figure(s, file, { x, y: CONTENT_TOP + 0.85, w: colW, h: 3.7 }, file);
    }
    caption(s, "Development year. Left: 2,190 stations. Right: 30,000 random station-days.", M, 6.08, 12);
    s.addText("The typical station-day is off by 1.6 bikes. Big stations can be off by much more, and that is what a daytime visit is for.", {
      x: M, y: 6.4, w: W - 2 * M, h: 0.5, fontSize: 15, bold: true, color: C.accent4, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("SPEAKER 3 (slides 6 and 7, about 2:30)\n\nA plan made the night before only works if tomorrow looks like the days before it. It does.\nOn the left each dot is a station: its average morning flow in odd weeks against even weeks. The correlation is 0.998, so stations keep their habits.\nOne day on its own is noisier. On the right is a single day against the average of the 10 workdays before it: correlation 0.90. The typical station-day is off by 1.6 bikes.\n\nIf asked why 10 days: we tried 5, 10 and 20 on the first year. 20 days cut shortages by 1% but moved 10% more bikes.");
  }

  // ---------- 7. Starting level ----------
  {
    const s = content("Analysis", "Most shortages come from starting the day at the wrong level");
    stat(s, "22%", "of workday station-days run empty or full at some point from a half-full start", M, CONTENT_TOP, 5.3, C.accent3, 36);
    stat(s, "1.3%", "would fail from any starting level, because the day's swing is larger than the docks", 6.9, CONTENT_TOP, 5.8, C.accent5, 36);
    const f = await figure(s, "fig8-one-day.png", { x: M, y: 3.0, w: 12.1, h: 3.6 }, "one day at three stations");
    caption(s, "Bikes docked on Tue 12 May 2026. Dashed: the station's docks. Flat at the dashes or at zero = riders turned away.", M, f.y + f.h + 0.02, 12.1);
    s.addNotes("Start every station half full and it runs empty or full at some point on 22% of workday station-days. On only 1.3% of them would every starting level have failed. So nearly all of it comes down to the starting level.\nHere is one normal Tuesday at three stations.\nBroadway and W 25 St is an office station with 109 docks. Starting half full, it is full by 08:45 and turns away the morning arrivals. Our start of 5 bikes holds out almost an hour longer.\nE 10 St and Ave A is a home station, the opposite case. Starting half full, it is empty from 09:00 to 16:00. Starting near full keeps bikes there all day.\n9 Ave and W 33 St is next to Penn Station. Its swing is 181 bikes and it has 94 docks, so no start works. Those stations come back at the end.");
  }

  // ---------- 8. Band ----------
  pres.addSection({ title: "The rule" });
  {
    const s = content("The rule", "Each station gets a target band from its own last ten days");
    // the station as a bar from empty to full docks
    const bx = M, by = 2.35, bw = 6.4, bh = 0.7;
    s.addText("One station at 04:00", { x: bx, y: CONTENT_TOP + 0.05, w: 6, h: 0.4, fontSize: 16, bold: true, color: C.accent6, margin: 0, isTextBox: true });
    s.addShape(pres.shapes.RECTANGLE, { x: bx, y: by, w: bw, h: bh, fill: { color: C.background2 }, line: { color: C.accent5, width: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x: bx + 2.4, y: by, w: 1.8, h: bh, fill: { color: C.accent1 }, line: { type: "none" } });
    s.addText("target band", { x: bx + 2.4, y: by, w: 1.8, h: bh, fontSize: 14, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText("0 bikes", { x: bx, y: by + bh + 0.05, w: 1.5, h: 0.3, fontSize: 12, color: C.accent6, margin: 0, isTextBox: true });
    s.addText("all docks full", { x: bx + bw - 1.8, y: by + bh + 0.05, w: 1.8, h: 0.3, fontSize: 12, color: C.accent6, align: "right", margin: 0, isTextBox: true });
    const rules = [
      ["Below the band", "trucks add bikes up to its lower edge", C.accent3],
      ["Inside the band", "no visit", C.accent1],
      ["Above the band", "trucks take bikes down to its upper edge", C.accent3],
    ];
    rules.forEach(([head, body, color], i) => {
      const y = 3.75 + i * 0.85;
      s.addShape(pres.shapes.OVAL, { x: bx, y: y + 0.08, w: 0.28, h: 0.28, fill: { color }, line: { type: "none" } });
      s.addText([{ text: head + ": ", options: { bold: true } }, { text: body }], { x: bx + 0.45, y, w: 5.9, h: 0.45, fontSize: 16, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
    });
    s.addText("Then we rank every possible move in the city by the shortages it prevents and do the best ones first.", {
      x: bx, y: 6.2, w: 6.4, h: 0.65, fontSize: 14, bold: true, color: C.accent4, margin: 0, valign: "top", isTextBox: true,
    });
    // how the band is built
    const x = 7.5, w = W - M - x;
    card(s, x, CONTENT_TOP + 0.05, w, 5.35);
    s.addText("How the band is built", { x: x + 0.3, y: CONTENT_TOP + 0.25, w: w - 0.6, h: 0.4, fontSize: 17, bold: true, color: C.text1, margin: 0, isTextBox: true });
    const steps = [
      ["1", "Take the station's last 10 comparable days: workdays or weekends."],
      ["2", "From each day keep two numbers. Need: the most it fell below its 04:00 stock. Room: its docks minus the most it rose above."],
      ["3", "A start below the need runs empty, one above the room runs full. Count the riders lost for each start over the 10 days. The fewest sit between the 10th and 11th smallest of the 20 numbers."],
    ];
    steps.forEach(([n, t], i) => {
      const y = CONTENT_TOP + 0.85 + i * 1.25;
      s.addShape(pres.shapes.OVAL, { x: x + 0.3, y, w: 0.45, h: 0.45, fill: { color: C.accent1 }, line: { type: "none" } });
      s.addText(n, { x: x + 0.3, y, w: 0.45, h: 0.45, fontSize: 15, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
      s.addText(t, { x: x + 0.95, y: y - 0.04, w: w - 1.25, h: 1.3, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true });
    });
    s.addText("The overnight-stock rule of Raviv and Kolka (2013), with the station's own days in place of a demand model.", {
      x: x + 0.3, y: CONTENT_TOP + 5.25 - 0.6, w: w - 0.6, h: 0.55, fontSize: 11, color: C.accent6, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("SPEAKER 4 (slides 8 to 10, about 2:30)\n\nThis is the rule. Each station gets a target band, a range instead of one number. If it is below the band at night, trucks fill it to the bottom of the band. If it is above, they take bikes away down to the top. Inside the band, nobody visits. That is where the half-full reset wastes work: 27% of its moves are at stations already inside their band.\nOn the right is how we build the band. For each of the last 10 comparable days we take two numbers. The need is how far the station fell below its 04:00 stock. The room is how far it could rise before the docks were full. Start below the need and it runs empty. Start above the room and it runs full. Count the riders lost for every possible start over those 10 days, and the lowest total is between the 10th and 11th smallest of the 20 numbers.\nAfter that we rank every single-bike move in the city by how many shortages it prevents, and do the best ones first, up to a nightly budget.\n\nIf asked why a band and not one number: any start inside the band loses the same riders on those 10 days, so moving a bike there buys nothing.");
  }

  // ---------- 9. Weather ----------
  {
    const s = content("The rule", "Weather predicts how busy tomorrow is, so it sizes the night shift");
    const colW = 4.3;
    await figure(s, "fig6-demand-model.png", { x: M, y: CONTENT_TOP, w: colW, h: 4.5 }, "predicted vs actual");
    await figure(s, "fig7-demand-effects.png", { x: M + colW + 0.3, y: CONTENT_TOP, w: colW + 0.6, h: 4.5 }, "weather effects");
    caption(s, "Left: trips per day, test year; dashed = perfect forecast. Right: change in a day's trips, 95% intervals.", M, 6.1, 9.3);
    const x = 10.2;
    stat(s, "0.87", "R² on the test year; half of all days within 11%", x, CONTENT_TOP + 0.05, 2.5);
    stat(s, "-6.6%", "trips for each wet hour; Christmas week -45%", x, CONTENT_TOP + 1.65, 2.5, C.accent3);
    s.addText("Stretching station targets by the forecast made results worse, so targets stay on history.", {
      x, y: CONTENT_TOP + 3.25, w: 2.5, h: 1.9, fontSize: 14, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("The band decides where the bikes go. How many riders show up still depends on the weather and the season.\nWe fitted a linear regression of the log of each day's trips on the weather between 07:00 and 21:00 and the calendar, on the first year. On the test year it explains 87% of the day-to-day changes, and half of all days are within 11%.\nThe effects: 5 degrees warmer adds 21% up to about 22 degrees, and above that the heat costs 6%. Every wet hour costs 6.6%, so five wet hours take about a third off. 5 cm of snow in the last three days costs 20%. Christmas week loses 45%.\nWe also tried stretching each station's band by tomorrow's forecast. It gave more shortages and more bikes moved. Gammelli and others found the same in 2021. So the forecast tells you how big a crew to send, and history sets the targets.\n\nIf asked why log trips: weather changes trips by a percentage, not by a fixed number, so the effects read as percent changes.");
  }

  // ---------- 10. Settings ----------
  {
    const s = content("The rule", "Ten days of history, 3,000 a night, 100 stations at 14:00");
    const head = (t) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } });
    const rows = [
      [head("Setting"), head("Tried"), head("Chosen"), head("Why")],
      ["Days of history", "5, 10, 20", "10", "20 days cut shortages 1% for 10% more bikes moved"],
      ["Stretch band by forecast", "yes, no", "no", "more shortages and more bikes moved"],
      ["Daytime visit", "10:00, 12:00, 14:00", "14:00", "fewest shortages, right before offices empty"],
      ["Night budget, day stations", "250 to 9,000 bikes; 25 to 400 stations", "3,000 and 100", "fewest shortages without moving more than Citi Bike's 2,707 a day (Jan to Sep 2025)"],
    ];
    s.addTable(rows, {
      x: M, y: CONTENT_TOP + 0.1, w: W - 2 * M, colW: [2.9, 2.9, 1.6, 4.73],
      fontSize: 15, color: C.text1, border: { type: "solid", pt: 0.75, color: "D6D3CC" }, rowH: 0.7, valign: "middle", margin: [0.06, 0.12, 0.06, 0.12],
    });
    card(s, M, 5.35, W - 2 * M, 1.3, "E3ECF8");
    s.addText([
      { text: "The 3,000 counts every bike loaded or unloaded. ", options: { bold: true } },
      { text: "A bike moved is picked up once and dropped once, so the night moves about 1,900 bikes." },
    ], { x: M + 0.3, y: 5.35, w: W - 2 * M - 0.6, h: 1.3, fontSize: 16, color: C.accent4, margin: 0, valign: "middle", isTextBox: true });
    s.addNotes("We picked every setting on the first year and only then ran the test year.\nThe rule for picking was fewest shortages, without moving more bikes than Citi Bike reported for January to September 2025, which was 2,707 a day. That way we win on the same amount of work, not by moving more.\nSay the budget right. 3,000 counts loads plus unloads, so it is about 1,900 bikes moved a night. Above 4,000 it gets worse, because the extra moves chase small savings that are mostly noise in 10 days of history.");
  }

  // ---------- 11. Results ----------
  pres.addSection({ title: "Results" });
  {
    const s = content("Results", "62% fewer riders turned away, with 57% fewer bikes moved");
    const f = await figure(s, "fig9-tradeoff.png", { x: M, y: CONTENT_TOP + 0.1, w: 12.1, h: 4.75 }, "schedules compared");
    caption(s, "Test-year averages, 2,470 stations. Band known in advance = perfect foresight, a ceiling no real forecast reaches.", M, f.y + f.h + 0.1, 12.1);
    s.addText("That is 1.5 riders turned away per 100 trips, with about as many bikes moved as Citi Bike moves today.", {
      x: M, y: 6.45, w: 12.1, h: 0.45, fontSize: 16, bold: true, color: C.accent4, margin: 0, isTextBox: true,
    });
    s.addNotes("SPEAKER 5 (slides 11 to 13, about 2:30)\n\nThese are all the schedules replayed on the test year, which we never used to choose anything.\nNever moving a bike turns away 18,189 riders a day. The half-full reset moves 5,873 bikes and still turns away 4,732. Moving every station into its band: 2,032 riders for 3,321 bikes. The night budget on its own: 1,945 for 1,877. Our recommendation, the budget plus the 14:00 visit: 1,779 for 2,549. Against half full that is 62% fewer riders turned away with 57% fewer bikes moved.\nThe pale bar, 869, is the same rule if we knew every day in advance. No forecast gets there, but it shows what is left to win.\nThe budget also beats banding every station: 87 fewer riders turned away with 1,444 fewer bikes, because it skips the moves that save little.");
  }

  // ---------- 12. 14:00 visit ----------
  {
    const s = content("Results", "A 14:00 visit is the best use of extra bikes");
    const f = await figure(s, "fig12-shortages-by-hour.png", { x: M, y: CONTENT_TOP, w: 6.6, h: 5.0 }, "shortages by hour");
    caption(s, "Riders turned away per hour, test-year average.", M, f.y + f.h + 0.05, 6.6);
    const x = 7.7, w = W - M - x;
    s.addText("Shortages prevented per extra bike moved", { x, y: CONTENT_TOP + 0.05, w, h: 0.4, fontSize: 16, bold: true, color: C.accent6, margin: 0, isTextBox: true });
    s.addChart(pres.charts.BAR, [{ name: "prevented per bike", labels: ["14:00 visit, 100 stations", "Night budget 3,000 to 4,000"], values: [0.25, 0.06] }], {
      x, y: CONTENT_TOP + 0.5, w, h: 2.4, barDir: "bar", chartColors: [HEX.accent1, HEX.accent5],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelFontSize: 16, dataLabelFontBold: true, dataLabelColor: HEX.dk1,
      catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
      valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, valAxisMaxVal: 0.3, valAxisMinVal: 0,
      catAxisOrientation: "maxMin", barGapWidthPct: 60,
    });
    stat(s, "166", "fewer riders turned away a day, for 671 more bikes moved", x, CONTENT_TOP + 3.15, 2.4, C.accent1, 36);
    stat(s, "196", "at 17:00, the worst hour; 253 without the visit", x + 2.6, CONTENT_TOP + 3.15, w - 2.6, C.accent1, 36);
    s.addNotes("Look at when riders are turned away. With half full, 944 are turned away in the 08:00 hour alone, because the start was wrong. With our schedule the worst hour is 17:00, when the offices empty: 196 riders, or 253 without the afternoon visit.\nAt 14:00 vans go to the 100 stations where a top-up prevents the most shortages. That saves 166 riders a day for 671 extra bikes, 0.25 per bike. Spending the same extra effort at night, by raising the budget from 3,000 to 4,000, saves 0.06 per bike. The afternoon visit is four times as good.\n\nIf asked why 14:00 and not noon: we tried 10:00, 12:00 and 14:00 on the first year, and 14:00 had the fewest shortages. It comes right before the evening rush.");
  }

  // ---------- 13. Citi Bike's own moves ----------
  {
    const s = content("Results", "Our plan moves about as many bikes as Citi Bike does today");
    const f = await figure(s, "fig13-moves-vs-reported.png", { x: M, y: CONTENT_TOP, w: 6.6, h: 5.0 }, "moves vs reported");
    caption(s, "Bikes moved per day by month. May 2026 report not posted.", M, f.y + f.h + 0.05, 6.6);
    const x = 7.7, w = W - M - x;
    stat(s, "2,572", "bikes a day simulated, against 2,514 Citi Bike reports for the same eleven months", x, CONTENT_TOP + 0.05, w);
    stat(s, "0.92", "correlation across months: our moves rise and fall with Citi Bike's", x, CONTENT_TOP + 1.75, w);
    s.addText("Citi Bike cuts harder in winter (974 a day in February against our 1,790). Shortages drop too, from 2,730 a day in June to 250 in February, so the night budget can shrink in winter.", {
      x, y: CONTENT_TOP + 3.45, w, h: 1.7, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("Is this realistic? Citi Bike reports its moves to NYC DOT every month. Our schedule moves 2,572 bikes a day against its 2,514, and the two go up and down together across the months, with a correlation of 0.92.\nCiti Bike cuts back harder in winter. Shortages fall in winter too, so our budget could shrink in winter as well. It also fits the fleet: we keep 38,069 bikes docked at 04:00, and the fleet is about 39,000.\n\nIn the Q&A, be careful: Citi Bike's 2,514 includes valets and Bike Angels, not only trucks. We can say it is the same amount of work, not the same trucks.");
  }

  // ---------- 14. Bottleneck stations ----------
  pres.addSection({ title: "Limits and recommendations" });
  {
    const s = content("Limits and recommendations", "Seven stations are too small for their traffic");
    const f = await figure(s, "fig11-shortages-left.png", { x: M, y: CONTENT_TOP, w: 5.0, h: 5.15 }, "shortages left");
    caption(s, "Riders turned away per day, recommended schedule.", M, f.y + f.h + 0.05, 5.0);
    const x = 6.3, w = W - M - x;
    stat(s, "442", "riders a day still turned away at seven stations: a quarter of what is left", x, CONTENT_TOP + 0.05, w, C.accent3);
    const stations = [
      "North Moore St & Greenwich St (Tribeca)",
      "Greenwich St & Hubert St (Tribeca)",
      "Dock 72 Way & Market St (Navy Yard)",
      "9 Ave & W 33 St (Penn Station)",
      "1 Ave & E 68 St",
      "E 47 St & Park Ave",
      "E 50 St & Park Ave",
    ];
    s.addText(stations.map((t, i) => ({ text: `${i + 1}.  ${t}`, options: { breakLine: i < stations.length - 1 } })), {
      x, y: CONTENT_TOP + 1.7, w: w, h: 2.6, fontSize: 14, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 3, isTextBox: true,
    });
    s.addText("On a normal workday each swings by more than it has docks. They need more docks or a valet.", {
      x, y: CONTENT_TOP + 4.45, w, h: 0.8, fontSize: 15, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("SPEAKER 6 (slides 14 to 16, about 2:30)\n\nWhat is left sits in a few places. Seven stations hold a quarter of the shortages that remain, 442 riders a day. On a normal workday each of them swings by more than it has docks. The one at Penn Station, 9 Ave and W 33 St, swings 181 bikes with 94 docks.\nThese stations are a capacity problem, and moving bikes at 04:00 cannot fix them. They need more docks or a valet. Citi Bike already uses valets at its busiest stations.");
  }

  // ---------- 15. Limitations ----------
  {
    const s = content("Limits and recommendations", "What the public data cannot see");
    const items = [
      ["Riders who give up leave no record", "We undercount demand at stations that are often empty, so the real shortages are higher than ours. Every schedule sees the same trips, and the ranking still holds."],
      ["Stock is never measured", "We work it out from trips in 5-minute steps. Departures count before arrivals in each step, which adds a few shortages at the busiest stations."],
      ["Citi Bike's own plan is not public", "We compare with two simple rules and check our workload against its monthly reports."],
      ["No costs or routes", "There is no public cost per bike, and we don't plan van routes. Dock counts come from one day in Oct 2026, and the 81 stations without them are left out."],
    ];
    const cw = (W - 2 * M - 0.4) / 2, ch = 1.95;
    items.forEach(([head, body], i) => {
      const x = M + (i % 2) * (cw + 0.4);
      const y = CONTENT_TOP + 0.05 + Math.floor(i / 2) * (ch + 0.3);
      card(s, x, y, cw, ch);
      s.addText(String(i + 1), { x: x + 0.25, y: y + 0.2, w: 0.5, h: 0.5, fontSize: 26, bold: true, color: C.accent1, margin: 0, isTextBox: true });
      s.addText(head, { x: x + 0.85, y: y + 0.22, w: cw - 1.1, h: 0.45, fontSize: 17, bold: true, color: C.text1, margin: 0, isTextBox: true });
      s.addText(body, { x: x + 0.85, y: y + 0.72, w: cw - 1.1, h: ch - 0.85, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true });
    });
    s.addText([
      { text: "Where the next gain is: ", options: { bold: true } },
      { text: "with perfect foresight the same rule turns away 869 riders a day, against our 1,779. Better station forecasts, from events, school calendars or subway disruptions, could close part of that gap." },
    ], { x: M, y: 5.95, w: W - 2 * M, h: 0.85, fontSize: 15, color: C.accent4, margin: 0, valign: "top", isTextBox: true });
    s.addNotes("These are ranked by how much each could change the result.\nFirst, a rider who walks away from an empty station leaves no trip. So we undercount demand there, and the real number of riders turned away is higher than ours. Every schedule is replayed on the same trips, though, so the comparison still holds.\nSecond, the data never shows how many bikes are in a station. We work it out from trips.\nThird, Citi Bike doesn't publish its station-by-station moves. We compare with never moving and with half full instead, and check our workload against its monthly reports.\nFourth, we count bikes, not dollars, and we don't plan the van routes. A routing step, like the one O'Mahony and Shmoys built in 2015, would turn the nightly list into routes.\nThe gap to perfect foresight, 1,779 against 869, comes from day-to-day noise. Better station forecasts would help more than more tuning. Bike Angels could also take over part of the budget without any trucks.");
  }

  // ---------- 16. Recommendations ----------
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Limits and recommendations" });
    s.addText("Five changes, biggest effect first", { placeholder: "title" });
    const recs = [
      ["Replace the half-full reset with a target band per station", "2,700 fewer riders turned away, 2,552 fewer bikes moved"],
      ["Treat the seven high-swing stations as a capacity problem", "442 riders a day: add docks or valets"],
      ["Send vans to the 100 neediest stations at 14:00", "166 fewer shortages for 671 bikes, 0.25 per bike"],
      ["Cap the night at 3,000 loads and unloads, best moves first", "1,444 fewer bikes than banding every station, 87 fewer shortages"],
      ["Size the night shift from the weather forecast", "volume within 11%; targets stay on history"],
    ];
    recs.forEach(([head, evidence], i) => {
      const y = CONTENT_TOP + 0.05 + i * 0.95;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y, w: W - 2 * M, h: 0.8, fill: { color: "22344F" }, line: { type: "none" }, rectRadius: 0.06 });
      s.addText(String(i + 1), { x: M + 0.2, y, w: 0.5, h: 0.8, fontSize: 24, bold: true, color: "6FA3EA", margin: 0, valign: "middle", isTextBox: true });
      s.addText(head, { x: M + 0.8, y, w: 6.6, h: 0.8, fontSize: 17, bold: true, color: C.background1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(evidence, { x: M + 7.5, y, w: 4.4, h: 0.8, fontSize: 14, color: "C9D3E3", margin: 0, valign: "middle", isTextBox: true });
    });
    s.addText("Together: 1,779 riders turned away a day instead of 4,732, with 2,549 bikes moved instead of 5,873.", {
      x: M, y: 6.3, w: W - 2 * M, h: 0.6, fontSize: 18, bold: true, color: "6FA3EA", margin: 0, isTextBox: true,
    });
    s.addNotes("Ranked by how many riders each one saves on the test year.\nOne, replace the half-full reset with target bands, planned separately for workdays and weekends from each station's last 10 comparable days. This is the biggest gain: 2,700 fewer riders turned away and 2,552 fewer bikes moved.\nTwo, treat the seven stations as a capacity problem and give them docks or valets.\nThree, send vans to the 100 neediest stations at 14:00. It is the best use of extra bikes.\nFour, cap the night at 3,000 loads and unloads, about 1,900 bikes, best moves first. This mostly saves cost.\nFive, use the weather forecast to decide how many trucks and crews go out. The targets still come from each station's history.\n\nTo close: together this turns away 62% fewer riders than half full while moving 57% fewer bikes, about what Citi Bike moves today. Thank you, we're happy to take questions.");
  }

  // ---------- Backups ----------
  pres.addSection({ title: "Backup for Q&A" });
  {
    const s = content("Backup for Q&A", "Backup: members ride the rush hours; weekends ride midday");
    const f = await figure(s, "fig1-daily-rhythm.png", { x: M, y: CONTENT_TOP + 0.2, w: 12.1, h: 4.9 }, "daily rhythm");
    caption(s, "Average trips started per hour, development year.", M, f.y + f.h + 0.05, 12.1);
    s.addNotes("If asked why workdays and weekends are planned separately: members make the 08:00 and 17:00 peaks on workdays. Weekends and casual riders follow one smooth curve around midday.");
  }
  {
    const s = content("Backup for Q&A", "Backup: a quarter of the stations take 80% of the moves");
    const f = await figure(s, "fig10-where-vans-go.png", { x: M, y: CONTENT_TOP, w: 5.6, h: 5.15 }, "where vans go");
    caption(s, "Bikes handled per day, recommended schedule; blue mostly receive, red mostly give, grey left alone.", M, f.y + f.h + 0.05, 12);
    const x = 6.9, w = W - M - x;
    stat(s, "49%", "of all bikes handled are at the busiest 10% of stations", x, CONTENT_TOP + 0.05, w);
    stat(s, "67%", "of drop-offs are in Manhattan, 25% in Brooklyn; the Bronx and Jersey City need almost nothing", x, CONTENT_TOP + 1.75, w);
    s.addText("Drop-offs: Upper West Side and central Brooklyn, ready for the morning. Pick-ups: Chelsea, the Financial District and Brooklyn Heights.", {
      x, y: CONTENT_TOP + 3.5, w, h: 1.5, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("646 stations, about a quarter, do 80% of the work. Use this map if someone asks where the trucks go.");
  }
  {
    const s = content("Backup for Q&A", "Backup: why a lost rider must also fail to arrive");
    const head = (t) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } });
    s.addTable([
      [head("Riders turned away a day"), head("Simple model: every rider still arrives"), head("Our model: a lost rider never arrives")],
      ["Never move a bike", "2,173", "18,189"],
      ["Reset to half full", "4,230", "4,732"],
      ["Recommended", "1,530", "1,779"],
    ], {
      x: M, y: CONTENT_TOP + 0.1, w: W - 2 * M, colW: [3.7, 4.2, 4.2], fontSize: 16, color: C.text1,
      border: { type: "solid", pt: 0.75, color: "D6D3CC" }, rowH: 0.75, valign: "middle", margin: [0.06, 0.12, 0.06, 0.12],
    });
    s.addText("In the simple model never moving a bike looks better than half full. It is not: once lost riders stop refilling the stations downstream, it reaches 18,189. The order of the schedules that move bikes is the same in both.", {
      x: M, y: 4.8, w: W - 2 * M, h: 1.3, fontSize: 16, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes("Our first draft used the simple model. If someone saw an earlier version, this is why the headline changed.");
  }
  {
    const s = content("Backup for Q&A", "Backup: the data that would close the gap to 869");
    const items = [
      ["Riders who were turned away", "app searches and failed unlocks give true demand at stations that are often empty", "Citi Bike has it"],
      ["Bikes and free docks every minute", "real stock and working docks, instead of stock rebuilt from trips", "live feed public, history not"],
      ["Citi Bike's own moves", "separates riders' flow from Citi Bike's old plan, and scores that plan", "Citi Bike has it"],
      ["Events", "one-off spikes a 10-day average can't see, like Madison Square Garden", "partly public"],
      ["Subway disruptions", "riders switch to bikes along a line that goes down", "public (MTA)"],
    ];
    items.forEach(([head, body, source], i) => {
      const y = CONTENT_TOP + 0.05 + i * 0.95;
      card(s, M, y, W - 2 * M, 0.8);
      s.addText(String(i + 1), { x: M + 0.2, y, w: 0.5, h: 0.8, fontSize: 24, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(head, { x: M + 0.8, y, w: 3.9, h: 0.8, fontSize: 16, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(body, { x: M + 4.9, y, w: 4.9, h: 0.8, fontSize: 14, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(source, { x: M + 9.95, y, w: 2.0, h: 0.8, fontSize: 13, color: C.accent6, margin: 0, valign: "middle", isTextBox: true });
    });
    s.addText("Ranked by how much each would change the plan. Our own weather model was scored on the weather that happened, not the forecast, so its 11% miss is a best case.", {
      x: M, y: 6.4, w: W - 2 * M, h: 0.55, fontSize: 13, color: C.accent6, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes(
      "If asked how the plan could get better: the gap between our 1,779 and the 869 with perfect foresight is all forecasting, so better data is where the gain is.\n" +
      "The top three are data Citi Bike already collects and doesn't publish. Riders who were turned away would give true demand at the stations that are often empty, which are the ones whose bands we set too low. Minute-by-minute station status would replace the stock we rebuild from trips. And its own truck moves would let us score its real plan instead of half full.\n" +
      "Events and subway disruptions are public and could go into the model as they are.\n\n" +
      "If asked about the weather model: it was scored on the weather that actually happened. The night shift would be planned from the forecast, so the real miss would be a bit bigger than 11%. Office attendance, school calendars and costs are further down the list in our data doc."
    );
  }
  {
    const s = content("Backup for Q&A", "Backup: numbers people mix up");
    const items = [
      ["3,000", "is the night budget in bikes loaded plus unloaded; it moves about 1,900 bikes (1,877 a day on the test year)"],
      ["2,514", "is Citi Bike's reported moves a day, and includes valets and Bike Angels, not only trucks"],
      ["527", "bikes a day topped up from the depot under our schedule, because a rider at a full dock leaves the simulation with the bike"],
      ["5 riders", "a day out of 1,779 is how much the result moves if riders inside the same 5 minutes are reordered"],
    ];
    items.forEach(([value, label], i) => {
      const y = CONTENT_TOP + 0.1 + i * 1.3;
      s.addText(value, { x: M, y, w: 2.6, h: 0.9, fontSize: 34, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(label, { x: M + 2.8, y, w: 9.3, h: 0.9, fontSize: 16, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
    });
    s.addNotes("Read these before the talk. A sharp question will test exactly these numbers.");
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}

build();
