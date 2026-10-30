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
    s.addText("Fewer bikes,\nbetter aimed", { x: M, y: 1.8, w: 7, h: 2.4, fontSize: 60, bold: true, color: C.background1, margin: 0, valign: "top", isTextBox: true });
    s.addText("When and where Citi Bike should move its bikes, tested on a year of real riders", {
      x: M, y: 4.4, w: 6.3, h: 1.0, fontSize: 20, color: "C9D3E3", margin: 0, valign: "top", isTextBox: true,
    });
    const statBox = (y, value, label) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.3, y, w: 4.4, h: 1.85, fill: { color: "22344F" }, line: { type: "none" }, rectRadius: 0.08 });
      s.addText(value, { x: 8.6, y: y + 0.2, w: 4, h: 0.9, fontSize: 54, bold: true, color: "6FA3EA", margin: 0, isTextBox: true });
      s.addText(label, { x: 8.6, y: y + 1.1, w: 4, h: 0.6, fontSize: 16, color: C.background1, margin: 0, isTextBox: true });
    };
    statBox(1.6, "62%", "fewer riders turned away");
    statBox(3.75, "57%", "fewer bikes moved");
    s.addText("than resetting every station to half full each night", { x: 8.3, y: 5.75, w: 4.4, h: 0.5, fontSize: 13, color: "C9D3E3", margin: 0, isTextBox: true });
    s.addNotes(
      "SPEAKER 1 (about 2:30 for slides 1 to 3)\n\n" +
      "Open with the answer: our schedule turns away 62% fewer riders than resetting stations to half full, and moves 57% fewer bikes doing it.\n" +
      "Then: in the next 15 minutes we show where that comes from, using every Citi Bike trip from October 2024 to September 2026.\n\n" +
      "Hook if you want one: picture a commuter at 8:45 who finds an empty station. That rider is lost. Our job is to have fewer of them for each bike Citi Bike pays to move."
    );
  }

  // ---------- 2. The imbalance ----------
  {
    const s = content("Problem", "Every workday morning, homes drain into the offices");
    const f = await figure(s, "fig2-rush-map.png", { x: M, y: CONTENT_TOP, w: 7.9, h: 5.15 }, "rush map");
    caption(s, "Bikes each station gains over a workday rush; red loses, blue gains. Development year.", M, f.y + f.h + 0.05, 7.9);
    const x = 9.0;
    stat(s, "9,400", "trips start in the 08:00 hour of a workday", x, 1.6, 3.7);
    stat(s, "1,055", "bikes leave Brooklyn each morning rush, while Manhattan gains 935", x, 3.15, 3.7, C.accent3);
    s.addText("Home stations run empty, office stations run full, and the evening runs it back.", {
      x, y: 4.75, w: 3.7, h: 1.3, fontSize: 16, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes(
      "The flow on this map is the problem. Red stations lose bikes in the morning rush, blue gain them.\n" +
      "Numbers: 9,400 trips start in the 08:00 hour. 417 stations lose 5 or more bikes in the morning rush and 294 gain 5 or more. Manhattan gains 935 bikes, Brooklyn loses 1,055. The evening reverses it: Manhattan loses 1,263.\n" +
      "Why it matters: the next rider at a red station finds no bike, the next at a blue one finds no dock. Both are lost trips.\n\n" +
      "Likely question: why are the Bronx and Jersey City grey? Their flows are small and balanced, so they need little attention."
    );
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
    s.addText("It publishes bikes moved per month, but not targets or shortages. So we score against two benchmarks:", {
      x, y: CONTENT_TOP + 3.6, w: 5.73, h: 0.7, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    [["Never move a bike", 0], ["Reset every station to half full each night", 1]].forEach(([t, i]) => {
      card(s, x + i * 2.5, CONTENT_TOP + 4.45, i ? 3.23 : 2.3, 0.85);
      s.addText(t, { x: x + i * 2.5 + 0.2, y: CONTENT_TOP + 4.45, w: (i ? 3.23 : 2.3) - 0.4, h: 0.85, fontSize: 14, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
    });
    s.addNotes(
      "Citi Bike already fights this with four tools: trucks, bike trains, valets and Bike Angels. It reports about 2,500 bikes moved a day to NYC DOT.\n" +
      "But it does not publish which stations it fills, to what level, or how many riders still find a station empty. So its plan cannot be scored directly.\n" +
      "Our question (read it). We measure against two simple benchmarks, and we check our workload against the moves Citi Bike reports.\n\n" +
      "Likely question: is half full what Citi Bike does? No, its method is not public. Half full is a common, simple rule we use as a yardstick."
    );
  }

  // ---------- 4. Method ----------
  pres.addSection({ title: "Data and method" });
  {
    const s = content("Data and method", "We replay 92 million real trips through any schedule");
    const steps = [
      ["92.1M trips", "every Citi Bike trip, Oct 2024 to Sep 2026, with start and end station and time"],
      ["Stock every 5 min", "bikes in each of 2,470 stations rebuilt from trips leaving and arriving"],
      ["Replay a schedule", "set each station's level at 04:00, then let the real riders come"],
      ["Count the cost", "riders turned away at an empty or full station, and bikes moved"],
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
    s.addText("Split by time, so nothing is tuned on the year it is scored on", { x: M, y: ty, w: 12, h: 0.4, fontSize: 16, bold: true, color: C.accent6, margin: 0, isTextBox: true });
    const half = (W - 2 * M - 0.2) / 2;
    s.addShape(pres.shapes.RECTANGLE, { x: M, y: ty + 0.55, w: half, h: 0.9, fill: { color: C.accent5 }, line: { type: "none" } });
    s.addShape(pres.shapes.RECTANGLE, { x: M + half + 0.2, y: ty + 0.55, w: half, h: 0.9, fill: { color: C.accent1 }, line: { type: "none" } });
    s.addText([{ text: "Development year  ", options: { bold: true } }, { text: "Oct 2024 to Sep 2025: explore, choose every setting" }], {
      x: M + 0.2, y: ty + 0.55, w: half - 0.4, h: 0.9, fontSize: 15, color: C.background1, margin: 0, valign: "middle", isTextBox: true,
    });
    s.addText([{ text: "Test year  ", options: { bold: true } }, { text: "Oct 2025 to Sep 2026: scored once" }], {
      x: M + half + 0.4, y: ty + 0.55, w: half - 0.4, h: 0.9, fontSize: 15, color: C.background1, margin: 0, valign: "middle", isTextBox: true,
    });
    s.addText("A rider turned away at an empty station never rides, so that bike never reaches the other end. Shortages ripple downstream.", {
      x: M, y: ty + 1.7, w: 12.1, h: 0.7, fontSize: 15, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes(
      "SPEAKER 2 (about 2:30 for slides 4 and 5)\n\n" +
      "The data only records trips, not how many bikes sit in a station. So we rebuild each station's stock: bikes arriving minus bikes leaving, in 5-minute steps, for 2,470 stations.\n" +
      "That turns the public data into a simulator. Pick a schedule, set every station's level at 04:00, the quietest hour, and replay the real riders. When a station is empty or full, that rider is turned away, and we count it.\n" +
      "Cleaning: station ids written with one decimal (7293.10 as 7293.1), depots and demo units listed as stations, 512 repeated trips, and 23 Feb 2026 when the system shut for 22 cm of snow. After fixes 99.9% of trips start at a public station.\n" +
      "We split by time: every setting is chosen on the first year, and the second year is used once to score.\n\n" +
      "Likely question: why does a lost rider matter downstream? If they never ride, the bike they would have delivered never arrives, so the next station is short too. A simpler model that ignores this flatters 'never rebalance' (2,173 vs 18,189 riders a day)."
    );
  }

  // ---------- 5. Clock ----------
  {
    const s = content("Data and method", "Each neighbourhood runs on its own clock");
    const f = await figure(s, "fig3-neighbourhood-clock.png", { x: M, y: CONTENT_TOP, w: 8.6, h: 5.15 }, "neighbourhood clock");
    caption(s, "Bikes gained per workday hour, 24 neighbourhoods with the largest swings. Development year.", M, f.y + f.h + 0.05, 8.6);
    const x = 9.6;
    stat(s, "726", "bikes leave the East Village over the morning rush", x, 1.6, 3.1, C.accent3);
    stat(s, "1,119", "arrive in Midtown and Times Square over the same hours", x, 3.1, 3.1);
    s.addText("Offices drain in a sharp window from 16:00 to 19:00, so a visit at 14:00 can still help them.", {
      x, y: 4.65, w: 3.1, h: 1.6, fontSize: 15, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes(
      "Each row is a neighbourhood, each column an hour. Red: losing bikes, blue: gaining.\n" +
      "Homes at the top empty from 06:00 to 10:00; offices at the bottom fill over the same hours. The evening runs it back.\n" +
      "Two details shape the schedule. Nightlife areas like Williamsburg and the West Village lose bikes again after 21:00. And the office districts drain between 16:00 and 19:00, which is why a 14:00 visit can still help.\n\n" +
      "Bridge to next speaker: the pattern is strong, but can we plan it the night before?"
    );
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
    s.addText("At most stations a night-before plan is off by a little (median miss 1.6 bikes); at the big ones by a lot, which is what a daytime visit is for.", {
      x: M, y: 6.4, w: W - 2 * M, h: 0.5, fontSize: 15, bold: true, color: C.accent4, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes(
      "SPEAKER 3 (about 2:30 for slides 6 and 7)\n\n" +
      "A night-before plan only works if tomorrow looks like the past. It does.\n" +
      "Left: each dot is a station, its average morning flow in odd weeks against even weeks. Correlation 0.998: stations keep their habits.\n" +
      "Right: a single day is noisier. Against the average of the 10 workdays before, correlation 0.90, and the median station-day misses by 1.6 bikes.\n\n" +
      "Likely question: why 10 days? We tried 5, 10 and 20 on the development year. 20 cut shortages by 1% for 10% more bikes moved, so 10."
    );
  }

  // ---------- 7. Starting level ----------
  {
    const s = content("Analysis", "Most shortages are a wrong starting level, not too few docks");
    stat(s, "22%", "of workday station-days run empty or full at some point from a half-full start", M, CONTENT_TOP, 5.3, C.accent3, 36);
    stat(s, "1.3%", "would fail from any starting level, because the day's swing is larger than the docks", 6.9, CONTENT_TOP, 5.8, C.accent5, 36);
    const f = await figure(s, "fig8-one-day.png", { x: M, y: 3.0, w: 12.1, h: 3.6 }, "one day at three stations");
    caption(s, "Bikes docked on Tue 12 May 2026. Dashed: the station's docks. Flat at the dashes or at zero = riders turned away.", M, f.y + f.h + 0.02, 12.1);
    s.addNotes(
      "Starting half full, a station runs empty or full on 22% of workday station-days. On only 1.3% would no starting level have worked. So almost every shortage is the wrong starting level.\n" +
      "One ordinary Tuesday at three stations:\n" +
      "Broadway and W 25 St, an office station with 109 docks. Half full is full by 08:45 and turns away the morning arrivals. Our start of 5 bikes holds almost an hour longer.\n" +
      "E 10 St and Ave A, a home station: the mirror image. Half full is empty from 09:00 to 16:00; starting near full keeps bikes there all day.\n" +
      "9 Ave and W 33 St, by Penn Station: the swing is 181 bikes against 94 docks. No start saves it. We come back to these stations at the end."
    );
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
      ["Inside the band", "leave it alone, no visit", C.accent1],
      ["Above the band", "trucks take bikes down to its upper edge", C.accent3],
    ];
    rules.forEach(([head, body, color], i) => {
      const y = 3.75 + i * 0.85;
      s.addShape(pres.shapes.OVAL, { x: bx, y: y + 0.08, w: 0.28, h: 0.28, fill: { color }, line: { type: "none" } });
      s.addText([{ text: head + ": ", options: { bold: true } }, { text: body }], { x: bx + 0.45, y, w: 5.9, h: 0.45, fontSize: 16, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
    });
    s.addText("Then rank every possible move across the city by the shortages it prevents, and do the best first.", {
      x: bx, y: 6.2, w: 6.4, h: 0.65, fontSize: 14, bold: true, color: C.accent4, margin: 0, valign: "top", isTextBox: true,
    });
    // how the band is built
    const x = 7.5, w = W - M - x;
    card(s, x, CONTENT_TOP + 0.05, w, 5.35);
    s.addText("How the band is built", { x: x + 0.3, y: CONTENT_TOP + 0.25, w: w - 0.6, h: 0.4, fontSize: 17, bold: true, color: C.text1, margin: 0, isTextBox: true });
    const steps = [
      ["1", "Take the station's last 10 comparable days: workdays or weekends."],
      ["2", "From each day keep two numbers. Need: the most it fell below its 04:00 stock. Room: its docks minus the most it rose above."],
      ["3", "Any start below the need, or above the room, turns riders away. The band is the start with the fewest over all 10 days: between the 10th and 11th smallest of the 20 numbers."],
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
    s.addNotes(
      "SPEAKER 4 (about 2:30 for slides 8 to 10)\n\n" +
      "This is the rule. Every station gets a target band, not a single number. Below it, trucks bring it up to the lower edge. Above it, they take it down to the upper edge. Inside it, nobody visits. That is where half full wastes effort: 27% of its moves go to stations already inside their band.\n" +
      "How the band is built (right): for each of the last 10 comparable days, the need is how far the station fell below its morning stock, the room is how far it could rise before the docks are full. A start below the need runs empty, above the room runs full. Count the riders turned away for every possible start over the 10 days: the lowest total sits between the 10th and 11th smallest of those 20 numbers.\n" +
      "Then we rank every single-bike move across the city by how many shortages it prevents and take the best first, up to a nightly budget.\n\n" +
      "Likely question: why a band and not one target? Inside the band, every start turns away the same number of riders on those 10 days, so moving a bike there buys nothing."
    );
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
    s.addText("Station targets still come from history: stretching them by the forecast made decisions worse.", {
      x, y: CONTENT_TOP + 3.25, w: 2.5, h: 1.9, fontSize: 14, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes(
      "The band handles where. The total number of riders still swings with the weather and season.\n" +
      "A linear regression of the log of each day's trips on the weather in riding hours (07:00 to 21:00) and the calendar, fitted on the development year, explains 87% of the day-to-day variation in the test year. Median error 11%.\n" +
      "Effects: each 5 degrees warmer adds 21% up to about 22 C, above that heat costs 6%. Each wet hour costs 6.6%, so five wet hours lose about a third. 5 cm of snow in the last three days costs 20%. Christmas week loses 45%.\n" +
      "Surprise worth saying: we tried stretching each station's band by tomorrow's forecast. It gave more shortages and more bikes moved. A good forecast of volume does not make a good station decision (Gammelli et al. 2021 find the same). So the forecast sizes the shift, history sets the targets.\n\n" +
      "Likely question: why log trips? Weather changes trips by a percentage, not a fixed number, so the effects read as percent changes."
    );
  }

  // ---------- 10. Settings ----------
  {
    const s = content("The rule", "Every setting was chosen before the test year was opened");
    const head = (t) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } });
    const rows = [
      [head("Setting"), head("Tried"), head("Chosen"), head("Why")],
      ["Days of history", "5, 10, 20", "10", "20 days cut shortages 1% for 10% more bikes moved"],
      ["Stretch band by forecast", "yes, no", "no", "more shortages and more bikes moved"],
      ["Daytime visit", "10:00, 12:00, 14:00", "14:00", "fewest shortages, just before offices drain"],
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
    s.addNotes(
      "Every setting was fixed on the development year. The test year was opened once, to score.\n" +
      "The budget rule: we chose the settings with the fewest shortages that do not move more bikes than Citi Bike reported for January to September 2025, 2,707 a day. So we compete on the same workload, not by moving more.\n" +
      "Say the budget correctly: 3,000 is bikes loaded plus unloaded, about 1,900 bikes moved a night. Past 4,000, extra moves make things worse, because they chase small savings that are mostly noise in 10 days of history."
    );
  }

  // ---------- 11. Results ----------
  pres.addSection({ title: "Results" });
  {
    const s = content("Results", "62% fewer riders turned away, with 57% fewer bikes moved");
    const f = await figure(s, "fig9-tradeoff.png", { x: M, y: CONTENT_TOP + 0.1, w: 12.1, h: 4.75 }, "schedules compared");
    caption(s, "Test-year averages, 2,470 stations. Band known in advance = perfect foresight, a ceiling no real forecast reaches.", M, f.y + f.h + 0.1, 12.1);
    s.addText("1.5 riders turned away per 100 trips, moving about what Citi Bike moves today.", {
      x: M, y: 6.45, w: 12.1, h: 0.45, fontSize: 16, bold: true, color: C.accent4, margin: 0, isTextBox: true,
    });
    s.addNotes(
      "SPEAKER 5 (about 2:30 for slides 11 to 13)\n\n" +
      "Every schedule replayed on the test year it never saw.\n" +
      "Never moving a bike: 18,189 riders turned away a day. Half full: 5,873 bikes moved and still 4,732 turned away. Every station into its band: 2,032 for 3,321 bikes. Night budget alone: 1,945 for 1,877. Recommended, budget plus the 14:00 visit: 1,779 for 2,549. That is 62% fewer shortages with 57% fewer bikes than half full.\n" +
      "The pale bar is perfect foresight, 869: the same rule if we knew each day in advance. No real forecast gets there; it shows what is left to win.\n" +
      "Key point: fewer, better-aimed moves beat more moves. The budget turns away 87 fewer riders than moving every station into its band, with 1,444 fewer bikes."
    );
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
    s.addNotes(
      "Where do shortages happen? The grey line is half full: 944 riders turned away in the 08:00 hour alone, because the start was wrong. Under our schedule the worst hour is 17:00, when offices drain: 196 riders, 253 without the visit.\n" +
      "The 14:00 visit sends vans to the 100 stations where moving them back to their rest-of-day band prevents most. It prevents 166 shortages a day for 671 more bikes: 0.25 per bike. Spending the same extra effort at night, raising the budget from 3,000 to 4,000, prevents 0.06 per bike. Four times better.\n\n" +
      "Likely question: why 14:00 and not noon? We tried 10, 12 and 14 on the development year; 14:00 had the fewest shortages because it comes just before the evening drain."
    );
  }

  // ---------- 13. Citi Bike's own moves ----------
  {
    const s = content("Results", "It asks for about the work Citi Bike already does");
    const f = await figure(s, "fig13-moves-vs-reported.png", { x: M, y: CONTENT_TOP, w: 6.6, h: 5.0 }, "moves vs reported");
    caption(s, "Bikes moved per day by month. May 2026 report not posted.", M, f.y + f.h + 0.05, 6.6);
    const x = 7.7, w = W - M - x;
    stat(s, "2,572", "bikes a day simulated, against 2,514 Citi Bike reports for the same eleven months", x, CONTENT_TOP + 0.05, w);
    stat(s, "0.92", "correlation across months: our moves rise and fall with Citi Bike's", x, CONTENT_TOP + 1.75, w);
    s.addText("Citi Bike cuts harder in winter (974 a day in February against our 1,790). Shortages drop too, from 2,730 a day in June to 250 in February, so the night budget can shrink in winter.", {
      x, y: CONTENT_TOP + 3.45, w, h: 1.7, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes(
      "Is this realistic? Citi Bike reports its monthly moves to NYC DOT. Our schedule moves 2,572 bikes a day against its 2,514, and the two rise and fall together, correlation 0.92.\n" +
      "Citi Bike scales down harder in winter. Shortages fall in winter too, so our budget could shrink with the season. It also fits the fleet: 38,069 bikes docked at 04:00 against a fleet of about 39,000.\n\n" +
      "Careful in Q&A: Citi Bike's 2,514 includes valets and Bike Angels, not just trucks. So the honest claim is 'the same order of work', not 'the same trucks'."
    );
  }

  // ---------- 14. Bottleneck stations ----------
  pres.addSection({ title: "Limits and recommendations" });
  {
    const s = content("Limits and recommendations", "Seven stations need docks or valets, not trucks");
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
    s.addText("Each swings by more than its docks on a typical workday, so no starting level saves it.", {
      x, y: CONTENT_TOP + 4.45, w, h: 0.8, fontSize: 15, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    });
    s.addNotes(
      "SPEAKER 6 (about 2:30 for slides 14 to 16)\n\n" +
      "What is left is concentrated. Seven stations hold a quarter of the remaining shortages, 442 riders a day. Each swings by more than its docks on a normal workday: Penn Station's 9 Ave and W 33 St swings 181 bikes with 94 docks.\n" +
      "For these, the problem is capacity. Moving bikes at 04:00 cannot fix it. They need more docks or a valet, which Citi Bike already uses at its busiest stations."
    );
  }

  // ---------- 15. Limitations ----------
  {
    const s = content("Limits and recommendations", "What the public data cannot see");
    const items = [
      ["Riders who give up leave no record", "So demand at often-empty stations is undercounted, and our shortage counts are lower bounds. Every schedule faces the same trips, so the ranking holds."],
      ["Stock is never measured", "We rebuild it from trips in 5-minute steps; in each step departures go before arrivals, which slightly overstates shortages at the busiest stations."],
      ["Citi Bike's own plan is not public", "So we compare with two benchmarks and check the workload against its monthly reports, not against its targets."],
      ["Bikes moved, not dollars", "No route planning and no public cost per bike. Dock counts come from one day in Oct 2026; 81 stations without them are left out."],
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
      { text: "Next gain is better forecasts, not more tuning: ", options: { bold: true } },
      { text: "perfect foresight would turn away 869 riders a day against our 1,779. Events, school calendars and subway disruptions could close part of that gap." },
    ], { x: M, y: 5.95, w: W - 2 * M, h: 0.85, fontSize: 15, color: C.accent4, margin: 0, valign: "top", isTextBox: true });
    s.addNotes(
      "Ranked by how much each could move the result.\n" +
      "1. Riders who walk away from an empty station leave no trip, so we undercount demand there. Our shortages are lower bounds; the real number is higher. Because every schedule is replayed on the same trips, the comparison still holds.\n" +
      "2. The data never shows how many bikes are in a station. We calculate it from trips.\n" +
      "3. Citi Bike does not publish its station-by-station moves, so we compare with never moving and with half full, and check our workload against its reports.\n" +
      "4. We count bikes, not dollars, and do not plan van routes. A routing step (O'Mahony and Shmoys 2015) would turn the nightly list into routes.\n" +
      "Future work: the gap to perfect foresight, 1,779 against 869, is day-to-day noise, so station forecasts are worth more than tuning the rule. Bike Angels could also take part of the budget at no truck cost."
    );
  }

  // ---------- 16. Recommendations ----------
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Limits and recommendations" });
    s.addText("Five changes, ranked by the riders they keep", { placeholder: "title" });
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
    s.addText("Move fewer bikes, to the right stations, at the right time.", {
      x: M, y: 6.35, w: W - 2 * M, h: 0.55, fontSize: 22, bold: true, color: "6FA3EA", margin: 0, isTextBox: true,
    });
    s.addNotes(
      "Ranked by the riders each one stops turning away on the test year.\n" +
      "1. Target bands instead of half full: the biggest gain. Plan workdays and weekends separately from each station's last 10 comparable days.\n" +
      "2. Seven stations are a capacity problem: docks or valets.\n" +
      "3. A 14:00 visit to the 100 neediest stations, the best use of extra bikes.\n" +
      "4. Cap the night at 3,000 loads and unloads, about 1,900 bikes, best moves first. Mostly a cost saving.\n" +
      "5. Use the weather forecast to decide how many trucks and crews to send. Targets still come from each station's history.\n\n" +
      "Close: together this turns away 62% fewer riders than half full while moving 57% fewer bikes, about what Citi Bike moves today. Thank you, we are happy to take questions."
    );
  }

  // ---------- Backups ----------
  pres.addSection({ title: "Backup for Q&A" });
  {
    const s = content("Backup for Q&A", "Backup: members ride the rush hours; weekends ride midday");
    const f = await figure(s, "fig1-daily-rhythm.png", { x: M, y: CONTENT_TOP + 0.2, w: 12.1, h: 4.9 }, "daily rhythm");
    caption(s, "Average trips started per hour, development year.", M, f.y + f.h + 0.05, 12.1);
    s.addNotes("If asked why we plan workdays and weekends separately: members drive the 08:00 and 17:00 peaks on workdays, while weekends and casual riders follow one smooth midday curve.");
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
    s.addNotes("646 stations, about a quarter, take 80% of the work. If asked where the trucks go, use this map.");
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
    s.addNotes("Our first draft used the simple model, so if someone saw an earlier version, this is why the headline changed.");
  }
  {
    const s = content("Backup for Q&A", "Backup: numbers that are easy to mix up");
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
    s.addNotes("Read before the talk. These are the numbers a sharp question will test.");
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}

build();
