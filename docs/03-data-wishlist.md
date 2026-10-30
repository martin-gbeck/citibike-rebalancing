# Citi Bike rebalancing: the data we wish we had

Our plan turns away 1,779 riders a day. With every day known in advance, the same rule would turn away 869. That gap is forecasting: a station's day scatters around its 10-day habit (correlation 0.90, a typical miss of 1.6 bikes), and the big stations miss by much more. Every item below either shrinks that miss or fixes a number we currently have to guess.

Ranked by how much each would change the plan. The ranking is our judgement, not a measured effect.

## 1. Riders who were turned away

**What:** every time someone opens the app and finds no bike or no free dock near them, tries to unlock at an empty station, or ends a ride at a different station from the one they set out for.

**What it fixes:** today a rider who walks away leaves no trace, so demand at stations that are often empty is undercounted. Those are exactly the stations whose bands are set too low, because their history only shows the riders who got a bike. With this data the bands would be built on true demand, and every shortage count would be a real number instead of a lower bound.

**Who has it:** Citi Bike, through the app. Not public.

## 2. Bikes and free docks in every station, every minute

**What:** the station status history: bikes available, docks available and docks out of service, per station, minute by minute.

**What it fixes:** we rebuild stock from trips because stock is never published, and we use dock counts from one day in October 2026 for both years. Real status would give the true starting level at 04:00, how long each station really sat empty or full, and the docks that actually worked that day. The 81 stations we left out for missing dock counts would come back in.

**Who has it:** Citi Bike publishes the live status feed (GBFS) but not its history. Anyone can start archiving it today; a full back history only Citi Bike has.

## 3. Citi Bike's own moves

**What:** every truck, van and bike-train pick-up and drop-off, with station, time and number of bikes; valet bikes taken in per station and hour; Bike Angels trips.

**What it fixes:** the trips we see already include Citi Bike's own rebalancing, so part of each station's "habit" is really Citi Bike's old plan. Separating the two would give the riders' own flow. It would also let us score Citi Bike's actual plan against ours, instead of against half full.

**Who has it:** Citi Bike. Only monthly totals are public, in its reports to NYC DOT.

## 4. Events

**What:** concerts, games, parades, marathons and street closures, with venue, start and end time, and expected crowd.

**What it fixes:** one-off spikes that a 10-day average cannot see. 9 Ave & W 33 St, one of our seven worst stations, is a block from Madison Square Garden.

**Who has it:** partly public. NYC Open Data lists permitted street events; venue calendars are on venue sites.

## 5. Subway disruptions

**What:** delays, suspensions and planned weekend work on each line, by hour.

**What it fixes:** when a line goes down, riders switch to bikes along it, and the stations near its stops run empty in a way their history never showed.

**Who has it:** public. The MTA publishes real-time service alerts and planned work.

## 6. Office attendance

**What:** how many people are in the office on each weekday, by neighbourhood (badge swipes or building occupancy).

**What it fixes:** the workday pattern is a commute pattern. Mondays and Fridays, when fewer people go in, look like any workday to our rule but may behave like something in between.

**Who has it:** some of it is sold or published by building-access companies at city level. Neighbourhood level would need a data deal.

## 7. School and university calendars

**What:** term dates, breaks and exam weeks for NYC public schools and the big universities (NYU, Columbia, The New School).

**What it fixes:** the East Village and Greenwich Village move with the NYU calendar, and a break week looks nothing like the 10 days before it.

**Who has it:** public.

## 8. The weather forecast as it was issued

**What:** the hourly forecast for the next day as it stood the evening before, not the weather that actually happened.

**What it fixes:** our demand model is fitted and scored on observed weather, so its 11% typical miss is a best case. The night shift is planned from a forecast, so this is the number that would show how well crew sizing works for real.

**Who has it:** public. Open-Meteo, the source we already use, also keeps an archive of past forecasts.

## 9. Costs and routes

**What:** cost per truck hour, per crew and per bike handled, and the depot and truck locations.

**What it fixes:** not the forecast, but the comparison. Today every schedule is compared in bikes moved, because no cost per bike is public. With costs, the plan could be compared in dollars, and a routing step could turn the nightly list of moves into actual truck routes.

**Who has it:** Citi Bike and Lyft. Not public.

## What the first three have in common

Items 1 to 3 are data Citi Bike already collects and does not publish. They would change the plan the most: true demand at the stations that need it, true stock and capacity instead of a rebuilt guess, and a fair score against Citi Bike's own plan. Items 4 to 8 are mostly public and could be added to our model as they are.
