"""Script for "The Money Trap" — stickfigure-finance-explainer playbook.

Each scene is (visual, narration). The visual dict is interpreted by
scripts/render.py; narration is synthesized sentence-by-sentence by
scripts/tts.py. All numbers quoted were computed in advance:
  $300/mo @ 8%/yr (monthly compounding): 40y -> $1,047,302 ; 30y -> $447,108
  Alex 25-35 only ($36k) then left alone to 65 -> $600,195
  $100 at 3% inflation: 20y -> $55.37 ; 30y -> $41.20
  $5,000 card @ 24% APR paying $150/mo -> 56 months, ~$8,322 total
  $5 latte/day = $1,825/yr ; invested 30y @ 8% -> ~$226,659
  $500/mo 40y: 7% -> $1,312,407 ; 6% (1% fee) -> $995,745
"""

TITLE = "The Money Trap"
SUBTITLE = "Why Working Harder Won't Make You Rich (And What Will)"

G, R, B, Y, P = "#2E9E5B", "#E0483E", "#2F6FD6", "#F2A93B", "#7A52C7"

SCENES = [
    # ------------------------------------------------------------ HOOK
    (dict(type="title", title=TITLE, sub=SUBTITLE),
     "Meet Sam and Alex. They are the same age, they went to the same school, and they got the same job, at the same company, with the same salary."),
    (dict(type="stage", head="Same job. Same salary.", figs=[
        dict(who="sam", x=.3, mood="happy", act="wave", hold="briefcase"),
        dict(who="alex", x=.7, mood="happy", act="wave", hold="briefcase")],
        props=[dict(kind="cash", x=.5, y=.35, s=1.2, label="$50,000 / year")]),
     "Fifty thousand dollars a year each. Not rich, not poor. Just normal. And for the first few years, their lives look almost identical."),
    (dict(type="stage", head="30 years later...", figs=[
        dict(who="sam", x=.28, mood="sad", act="sweat", age=1),
        dict(who="alex", x=.72, mood="happy", act="cheer", age=1)],
        props=[dict(kind="money_bag", x=.86, y=.55, s=1.6, label="$1,000,000+"),
               dict(kind="card", x=.14, y=.55, s=1.2, label="debt", color=R)]),
     "But thirty years later, something strange has happened. Alex is a millionaire, ready to retire whenever Alex wants. Sam is still working, still stressed, and still has credit card debt."),
    (dict(type="stage", head="What happened?", figs=[
        dict(who="sam", x=.5, mood="confused", act="shrug", say="???")]),
     "Sam never got fired. Sam never gambled the house away. Sam never did anything that looked like a big mistake. So what happened?"),
    (dict(type="bullets", title="In this video", icon="num", items=[
        "Where the money actually goes", "The silent thief: inflation", "Debt: compounding against you",
        "Compounding working for you", "Assets vs. liabilities", "A simple plan anyone can follow"]),
     "In this video, we are going to follow Sam and Alex and uncover the money trap. We will look at where money really goes, the silent thief that shrinks your savings, how debt quietly compounds against you, and how the exact same math can work for you instead. And at the end, I will give you a simple plan that anyone can follow."),
    (dict(type="big", text="Not financial advice", sub="Just math, stick figures, and common sense", color=R),
     "Quick note before we start. This is general education, not personal financial advice. Your situation is unique. But the math you are about to see is the same for everyone."),

    # ------------------------------------------------------------ CH1
    (dict(type="chapter", n=1, title="Where Does the Money Go?"),
     "Chapter one. Where does the money go?"),
    (dict(type="stage", head="Payday!", figs=[dict(who="sam", x=.5, mood="happy", act="cheer")],
          fx="coins_rain"),
     "Let's start with Sam's first paycheck. After taxes, fifty thousand a year comes out to about thirty nine thousand. That's roughly three thousand two hundred and fifty dollars a month. It feels like a fortune."),
    (dict(type="stage", head="A little upgrade...", figs=[dict(who="sam", x=.25, mood="happy", act="point")],
          props=[dict(kind="car", x=.55, y=.62, s=1.4, label="new car", appear=.5),
                 dict(kind="phone", x=.82, y=.5, s=1.1, label="new phone", appear=3),
                 dict(kind="coffee", x=.7, y=.28, s=.9, label="daily latte", appear=6)]),
     "So Sam does what most people do. Sam finances a nice new car, because Sam deserves it. Gets the newest phone on a monthly plan. Grabs a fancy coffee every morning on the way to work. None of these feel like a big deal."),
    (dict(type="stage", head="The leaky bucket", figs=[dict(who="sam", x=.25, mood="confused", act="point")],
          props=[dict(kind="bucket", x=.62, y=.58, s=1.8, leak=True)], fx="pour"),
     "But here's the thing. Sam's money works like a bucket with holes in it. The paycheck pours in at the top, and it leaks out the bottom through dozens of small holes. Subscriptions. Delivery apps. Car payments. Little treats. By the end of the month, the bucket is empty again."),
    (dict(type="stat", value=1825, prefix="$", suffix=" / year", label="a $5 coffee, every working day... and weekends", color=R),
     "Take that coffee. Five dollars a day doesn't sound like much. But five dollars, every single day, is one thousand eight hundred and twenty five dollars a year."),
    (dict(type="big", text="It's not about the coffee.", sub="It's about the habit of never keeping anything.", color=B),
     "Now, this isn't a lecture about coffee. Enjoy your coffee. The real problem isn't any one purchase. It's that Sam has no system. Whatever comes in, goes out."),
    (dict(type="chapter", n=0, title="Lifestyle Inflation", small=True),
     "And then something even sneakier happens. Sam gets a raise."),
    (dict(type="line", title="Sam's income vs. spending", xlabel="years", x0=0, x1=10, money=True,
          series=[dict(name="income", color=G, data=[3250, 3400, 3550, 3700, 3900, 4100, 4300, 4500, 4700, 4900, 5100]),
                  dict(name="spending", color=R, data=[3200, 3380, 3540, 3700, 3890, 4100, 4290, 4500, 4700, 4890, 5100])]),
     "Every time Sam earns more, Sam spends more. A bigger apartment. A nicer car. Better vacations. Economists call this lifestyle inflation, or lifestyle creep. Look at the chart. Income goes up. But spending goes up right alongside it, like a shadow. The gap between them, the money Sam actually keeps, stays at almost zero."),
    (dict(type="stage", head="The rat race", figs=[dict(who="sam", x=.5, mood="sad", act="run", on="treadmill")]),
     "This is what people call the rat race. Running faster and faster, earning more and more, and somehow ending up in exactly the same place. Working harder doesn't fix it, because the problem isn't how much Sam earns. It's what happens after the money arrives."),
    (dict(type="stage", head="Alex does one thing differently", figs=[
        dict(who="alex", x=.35, mood="happy", act="point")],
        props=[dict(kind="piggy", x=.68, y=.6, s=1.6, label="pay yourself first")], fx="coin_drop"),
     "Alex earns exactly the same. Alex enjoys life too. But Alex does one thing differently. On payday, before spending a single dollar, Alex moves a fixed amount into savings and investments. Automatically. Alex pays future Alex first, and then spends whatever is left."),
    (dict(type="versus", left=dict(who="sam", mood="sad", title="Sam", lines=["Earn", "Spend", "Save what's left", "(nothing is left)"]),
          right=dict(who="alex", mood="happy", title="Alex", lines=["Earn", "Save first", "Spend what's left", "(always saves)"])),
     "It sounds like a tiny difference. Sam earns, spends, and tries to save whatever is left over. And there is never anything left over. Alex earns, saves first, and then spends what's left. Same income. Completely different outcome. Remember this, because it will matter a lot later."),

    # ------------------------------------------------------------ CH2
    (dict(type="chapter", n=2, title="The Silent Thief"),
     "Chapter two. The silent thief."),
    (dict(type="stage", head="Sam's 'safe' plan", figs=[dict(who="sam", x=.35, mood="happy", act="point")],
          props=[dict(kind="cash", x=.68, y=.36, s=1.3, label="cash under the mattress"),
                 dict(kind="sofa", x=.68, y=.7, s=1.5)]),
     "A few years in, Sam gets a little nervous and decides to save some money. But Sam doesn't trust the stock market. Too risky. So Sam keeps the savings in cash, or in a bank account paying almost no interest. That feels safe. Nothing can go wrong, right?"),
    (dict(type="stage", head="Prices keep rising", figs=[dict(who="sam", x=.3, mood="shocked", act="shock")],
          props=[dict(kind="burger", x=.62, y=.5, s=1.3, label="$5 -> $9"),
                 dict(kind="house", x=.85, y=.55, s=1.2, label="rent going up")]),
     "Wrong. There is a thief hiding in plain sight. It's called inflation. Every year, prices go up a little. The burger that cost five dollars a decade ago costs nine dollars now. Rent goes up. Groceries go up. Everything goes up."),
    (dict(type="bars", title="What $100 in cash can buy (3% inflation)", money=True, items=[
        ["today", 100, G], ["in 10 years", 74.41, Y], ["in 20 years", 55.37, Y], ["in 30 years", 41.20, R]]),
     "Let's say inflation averages three percent a year. That's a fairly normal number. If you keep one hundred dollars in cash, after ten years it only buys what seventy four dollars buys today. After twenty years, about fifty five dollars. After thirty years, just forty one dollars. You didn't spend it. You didn't lose it. But more than half of its value quietly disappeared."),
    (dict(type="big", text="Cash isn't safe.", sub="It just loses value slowly enough that you don't notice.", color=R),
     "So cash isn't actually safe over the long run. It just loses value slowly enough that you don't notice. Sam thinks Sam is avoiding risk. In reality, Sam is guaranteeing a slow loss."),
    (dict(type="stage", head="Keep SOME cash", figs=[dict(who="alex", x=.32, mood="happy", act="point")],
          props=[dict(kind="shield", x=.66, y=.5, s=1.6, label="emergency fund: 3-6 months")]),
     "Now, to be fair, you do need some cash. Alex keeps an emergency fund, enough to cover three to six months of essential expenses, in a high yield savings account. That's the shield. If Alex loses a job, or the car breaks down, there's no panic and no need for a credit card."),
    (dict(type="stage", head="...and put the rest to work", figs=[dict(who="alex", x=.3, mood="happy", act="cheer")],
          props=[dict(kind="tree", x=.68, y=.6, s=1.7, grow=True, label="investments")]),
     "But everything beyond the emergency fund, the long term money, Alex puts to work, in investments that have historically grown faster than inflation. We'll get to exactly how in a few minutes. First, we need to talk about the thing that's really hurting Sam."),

    # ------------------------------------------------------------ CH3
    (dict(type="chapter", n=3, title="Debt: The Trap Closes"),
     "Chapter three. Debt. The trap closes."),
    (dict(type="stage", head="Emergency!", figs=[dict(who="sam", x=.3, mood="shocked", act="shock")],
          props=[dict(kind="car", x=.7, y=.62, s=1.4, broken=True, label="repair: $5,000")]),
     "One day, Sam's car breaks down. The repair bill is five thousand dollars. Sam doesn't have an emergency fund. So Sam does the only thing Sam can do."),
    (dict(type="stage", head="Swipe.", figs=[dict(who="sam", x=.35, mood="neutral", act="point", hold="card")],
          props=[dict(kind="card", x=.7, y=.48, s=1.6, label="24% APR", color=R)]),
     "Sam puts it on a credit card. The interest rate is twenty four percent a year. That's pretty typical for credit cards. Sam plans to pay it off quickly. Sam can afford one hundred and fifty dollars a month."),
    (dict(type="stat", value=56, suffix=" months", label="to pay off $5,000 at 24% paying $150/month", color=R),
     "How long does that take? Fifty six months. Almost five years."),
    (dict(type="bars", title="The real cost of a $5,000 repair", money=True, items=[
        ["the repair", 5000, Y], ["interest paid", 3322, R], ["total paid", 8322, R]]),
     "And in total, Sam pays about eight thousand three hundred dollars. More than three thousand dollars of that is pure interest. Sam paid for the repair, and then paid for it again, more than half over, just for the privilege of borrowing."),
    (dict(type="stage", head="Compounding... against you", figs=[dict(who="sam", x=.5, mood="sad", act="walk", chain=True)]),
     "This is the dark side of something called compound interest. When you owe money, interest is charged on your balance, and if you don't pay it, interest is charged on the interest. The debt grows by itself. It is like a ball and chain that gets heavier every month you carry it."),
    (dict(type="stage", head="The car itself", figs=[dict(who="sam", x=.25, mood="confused", act="point")],
          props=[dict(kind="car", x=.62, y=.62, s=1.5, label="$35,000 -> ~$17,000 in 5 yrs"),
                 dict(kind="arrow_down", x=.88, y=.45, s=1.3, color=R)]),
     "And remember Sam's new car? Sam borrowed thirty five thousand dollars for it. Sam pays interest on that loan every month. Meanwhile, the car loses value the moment it leaves the dealership. After five years, it might be worth only half of what Sam paid. Sam is paying interest on something that is shrinking."),
    (dict(type="pie", title="Sam's monthly paycheck", items=[
        ["rent", 35, B], ["car loan", 15, R], ["card & loans", 12, R], ["food & fun", 30, Y], ["savings", 0, G], ["other", 8, P]]),
     "Put it all together and look at Sam's paycheck. Rent. Car loan. Credit card payments. Food and fun. Everything else. And savings? Zero. A big slice of Sam's income now goes to paying for the past, instead of building the future."),
    (dict(type="big", text="Debt = your future income, spent today", sub="plus interest", color=R),
     "That's what consumer debt really is. It's your future income, spent today, plus interest. Every dollar of debt is a dollar that future Sam has to earn, and then hand to the bank."),
    (dict(type="stage", head="Not all debt is equal", figs=[dict(who="alex", x=.5, mood="thinking", act="think")],
          props=[dict(kind="card", x=.18, y=.45, s=1.2, label="high interest: avoid", color=R),
                 dict(kind="house", x=.82, y=.5, s=1.3, label="low rate, long term: careful")]),
     "To be fair, not all debt is equally bad. A low interest mortgage on a home you can afford, or a loan for an education that clearly raises your income, can make sense. But high interest consumer debt, the kind used for stuff that loses value, is the single biggest wealth killer for normal people."),
    (dict(type="bullets", title="Alex's debt rules", icon="check", items=[
        "Credit card paid in full every month", "Emergency fund instead of borrowing",
        "Cars bought used, kept for years", "High-interest debt killed first"]),
     "Alex has a few simple rules. Pay the credit card in full, every month, so interest is never charged. Use the emergency fund, not debt, for surprises. Buy reliable used cars and drive them for a long time. And if there ever is high interest debt, pay it off before anything else. Because paying off a twenty four percent credit card is like earning a guaranteed twenty four percent return."),

    # ------------------------------------------------------------ CH4
    (dict(type="chapter", n=4, title="The Eighth Wonder of the World"),
     "Chapter four. The eighth wonder of the world."),
    (dict(type="big", text="Compound interest", sub="interest earning interest, earning interest...", color=G),
     "There's a famous quote, often attributed to Albert Einstein, though nobody can prove he said it. Compound interest is the eighth wonder of the world. He who understands it, earns it. He who doesn't, pays it. Sam has been paying it. Now let's see what happens when Alex earns it."),
    (dict(type="stage", head="The snowball", figs=[dict(who="alex", x=.25, mood="happy", act="push")],
          props=[dict(kind="snowball", x=.6, y=.62, s=1.0, grow=True)]),
     "Think of a snowball rolling down a hill. At first it's tiny. It picks up a little snow on each turn. But the bigger it gets, the more snow it picks up per turn. Growth creates more growth. That's compounding. Your money earns a return, and then that return starts earning its own return."),
    (dict(type="stage", head="Alex's plan", figs=[dict(who="alex", x=.3, mood="happy", act="point")],
          props=[dict(kind="calendar", x=.62, y=.45, s=1.2, label="every month"),
                 dict(kind="cash", x=.85, y=.5, s=1.0, label="$300")]),
     "Here's Alex's plan. Starting at age twenty five, Alex invests three hundred dollars a month. That's it. Not a fortune. About ten dollars a day. And let's assume an average return of eight percent a year. That's an assumption, not a promise, but it's in the range of what a broad stock market fund has returned over long periods of history."),
    (dict(type="line", title="$300/month at 8%: money in vs. money grown", xlabel="years", x0=0, x1=40, money=True,
          series=[dict(name="what Alex put in", color=B, data=[0, 18000, 36000, 54000, 72000, 90000, 108000, 126000, 144000]),
                  dict(name="what it grew to", color=G, data=[0, 22043, 54884, 103811, 176706, 285308, 447108, 688165, 1047302])]),
     "Watch what happens. For the first ten years, it's honestly boring. Alex puts in thirty six thousand dollars, and it grows to about fifty five thousand. Nice, but nothing special. After twenty years, about one hundred and seventy seven thousand. Then the curve starts to bend. After thirty years, four hundred and forty seven thousand. And after forty years, at age sixty five, over one million dollars."),
    (dict(type="bars", title="After 40 years", money=True, items=[
        ["Alex's own money", 144000, B], ["growth from compounding", 903302, G], ["total", 1047302, G]]),
     "Here's the incredible part. Alex only put in one hundred and forty four thousand dollars of actual money. The other nine hundred thousand dollars came from compounding. From returns earning returns. The money did most of the work."),
    (dict(type="stat", value=72, prefix="", suffix="", label="Rule of 72: years to double = 72 / return", color=B),
     "There's a handy shortcut called the rule of seventy two. Divide seventy two by your annual return, and you get roughly how many years it takes your money to double. At eight percent, seventy two divided by eight is nine. Your money roughly doubles every nine years. Over forty years, that's more than four doublings."),
    (dict(type="chapter", n=0, title="The Most Important Ingredient", small=True),
     "Now here's the most important part of this whole video. The secret ingredient of compounding isn't money. It's time."),
    (dict(type="versus", left=dict(who="alex", mood="happy", title="Alex: ages 25-35", lines=["$300/mo for 10 years", "$36,000 put in", "then stops forever", "at 65: $600,195"]),
          right=dict(who="sam", mood="sad", title="Sam: ages 35-65", lines=["$300/mo for 30 years", "$108,000 put in", "never stops", "at 65: $447,108"])),
     "Imagine a different story. Alex invests three hundred a month from twenty five to thirty five, just ten years, thirty six thousand dollars total, and then stops completely, and never adds another dollar. Sam wakes up at thirty five and invests three hundred a month for thirty straight years, a hundred and eight thousand dollars total. Who has more at sixty five?"),
    (dict(type="bars", title="At age 65", money=True, items=[
        ["Alex (10 yrs, $36k in)", 600195, G], ["Sam (30 yrs, $108k in)", 447108, B]]),
     "Alex. With about six hundred thousand dollars, versus Sam's four hundred and forty seven thousand. Alex put in one third of the money, and still ended up with more, simply by starting ten years earlier. Those early dollars had more time to snowball."),
    (dict(type="big", text="The best time to start was yesterday.", sub="The second best time is today.", color=G),
     "So if you take one thing from this video, let it be this. The best time to start was years ago. The second best time is today. Not when you earn more. Not when things calm down. Today, even if it's a small amount."),

    # ------------------------------------------------------------ CH5
    (dict(type="chapter", n=5, title="Assets vs. Liabilities"),
     "Chapter five. Assets versus liabilities."),
    (dict(type="versus", left=dict(who="sam", mood="confused", title="Liability", lines=["takes money", "out of your pocket", "car loan, gadgets,", "subscriptions"]),
          right=dict(who="alex", mood="happy", title="Asset", lines=["puts money", "into your pocket", "index funds, savings,", "a business, skills"])),
     "There's a simple way to think about everything you own. An asset puts money into your pocket. A liability takes money out of your pocket. A car loan, a big TV on credit, a pile of subscriptions. Those are liabilities. Investments, a business, or skills that raise your income. Those are assets."),
    (dict(type="stage", head="Looking rich vs. being rich", figs=[
        dict(who="sam", x=.28, mood="happy", act="wave", hold="phone"), dict(who="alex", x=.72, mood="neutral", act="idle")],
        props=[dict(kind="car", x=.12, y=.66, s=1.1, label="leased"), dict(kind="tree", x=.9, y=.62, s=1.1, grow=True, label="growing")]),
     "Here's the twist. Sam often looks richer than Alex. Nicer car, newer clothes, more expensive vacations. But looking rich and being rich are opposites. Every dollar Sam spends to look rich is a dollar that will never compound. Alex looks perfectly normal, while a money tree quietly grows in the background."),
    (dict(type="big", text="Wealth is what you DON'T see.", sub="The cars not bought. The money still invested.", color=G),
     "Wealth is mostly invisible. It's the car that wasn't bought, the upgrade that was skipped, the money that is still sitting in an account, compounding. You can't see someone's net worth by looking at their driveway."),
    (dict(type="stage", head="The best asset early on: you", figs=[dict(who="alex", x=.35, mood="happy", act="think", hold="book")],
          props=[dict(kind="arrow_up", x=.7, y=.45, s=1.5, color=G, label="income")]),
     "And early in life, your biggest asset is actually you. Your ability to earn. Alex spends some money on courses, certifications, and learning new skills, and over the years, that turns into promotions and raises. Investing in yourself is one of the few investments with no ceiling."),
    (dict(type="stage", head="Raises go to the future", figs=[dict(who="alex", x=.3, mood="happy", act="cheer")],
          props=[dict(kind="cash", x=.6, y=.4, s=1.0, label="+$5,000 raise"),
                 dict(kind="piggy", x=.82, y=.62, s=1.3, label="half saved")]),
     "And here's the key. When Alex gets a raise, Alex doesn't let lifestyle inflation swallow all of it. A simple rule: at least half of every raise goes straight to investments. Alex still gets to enjoy life a little more each year, but the gap between earning and spending keeps growing. That gap is the engine of wealth."),

    # ------------------------------------------------------------ CH6
    (dict(type="chapter", n=6, title="Where Should the Money Go?"),
     "Chapter six. Where should the money actually go?"),
    (dict(type="stage", head="Picking stocks?", figs=[dict(who="sam", x=.3, mood="shocked", act="shock")],
          props=[dict(kind="phone", x=.66, y=.48, s=1.4, label="hot tip!!"), dict(kind="arrow_down", x=.86, y=.48, s=1.2, color=R)]),
     "Sam finally decides to invest. Sam hears a hot tip from a friend, buys a single stock that everyone is talking about, and watches it drop forty percent in two months. Sam panics, sells, and decides investing is basically gambling."),
    (dict(type="stage", head="The index fund: buy the whole basket", figs=[dict(who="alex", x=.28, mood="happy", act="point")],
          props=[dict(kind="basket", x=.66, y=.6, s=1.8, label="hundreds of companies")]),
     "Alex does something much more boring. Instead of trying to pick the winners, Alex buys the whole basket. A broad, low cost index fund holds hundreds or even thousands of companies at once. When some go down, others go up. Alex doesn't need to be a genius. Alex just owns a small piece of the whole economy."),
    (dict(type="line", title="The market over time (illustration)", xlabel="years", x0=0, x1=30, money=False, wiggle=True,
          series=[dict(name="broad market", color=G, data=[100, 112, 98, 125, 140, 118, 150, 175, 160, 190, 230, 210, 260, 300, 270, 330, 380, 350, 420, 480, 400, 470, 550, 620, 580, 660, 760, 700, 820, 900, 1000])]),
     "Does the market go down? Absolutely. Sometimes a lot. Crashes and recessions happen every few years. But historically, over long periods, broad markets have gone up far more than they've gone down. The ride is bumpy, but the direction has been upward. The people who got hurt the most were usually the ones who panicked and sold at the bottom."),
    (dict(type="bars", title="$500/month for 40 years", money=True, items=[
        ["7% return, low fees", 1312407, G], ["same, minus 1% fee", 995745, R]]),
     "Alex also pays attention to fees. A one percent fee sounds tiny. But take five hundred dollars a month for forty years. At seven percent, you'd end up with about one point three million. With a one percent annual fee eating into that return, you'd end up with under one million. That small fee quietly costs over three hundred thousand dollars."),
    (dict(type="stage", head="Make it automatic", figs=[dict(who="alex", x=.3, mood="happy", act="idle", hold="phone")],
          props=[dict(kind="calendar", x=.66, y=.42, s=1.1, label="payday"), dict(kind="arrow_up", x=.86, y=.55, s=1.0, color=G, label="auto-invest")]),
     "And finally, Alex makes it automatic. On payday, money moves into the investment account without Alex having to decide anything. No willpower needed. No checking the news. No trying to guess the perfect moment. Alex basically forgets about it and lets time do its thing."),
    (dict(type="stage", head="Use the tax breaks", figs=[dict(who="alex", x=.35, mood="happy", act="point")],
          props=[dict(kind="building", x=.72, y=.55, s=1.5, label="retirement accounts")]),
     "If your employer offers a retirement plan, especially one with a matching contribution, that match is basically free money. Take it. Many countries also have tax advantaged accounts for long term investing. The exact rules depend on where you live, so it's worth spending an afternoon learning what's available to you."),

    # ------------------------------------------------------------ CH6b
    (dict(type="chapter", n=0, title="Three Excuses That Keep People Trapped", small=True),
     "Before we get to the plan, let's deal with the three excuses that keep most people stuck in the trap. Sam has used all three."),
    (dict(type="stage", head="Excuse #1: \"I don't earn enough\"", figs=[dict(who="sam", x=.3, mood="sad", act="shrug")],
          props=[dict(kind="coin", x=.62, y=.5, s=1.6, label="$50 / month"), dict(kind="arrow_up", x=.84, y=.5, s=1.1, color=G)]),
     "Excuse number one. I don't earn enough to invest. It's true that a bigger income makes everything easier. But the habit matters more than the amount. Fifty dollars a month is a real start. It builds the system, and when the income grows, the system is already there, waiting. Plenty of high earners are broke, because the habit never formed."),
    (dict(type="stage", head="Excuse #2: \"I'll start later\"", figs=[dict(who="sam", x=.3, mood="neutral", act="idle")],
          props=[dict(kind="clock", x=.68, y=.48, s=1.6, label="tick, tock")]),
     "Excuse number two. I'll start later. After the next raise. After the wedding. After things calm down. But things never calm down. And as we saw, every year you wait costs you the most powerful years of compounding, the ones at the very end, where the snowball is biggest. Waiting ten years can cut your final result by more than half."),
    (dict(type="stage", head="Excuse #3: \"I'll wait for the right moment\"", figs=[dict(who="sam", x=.3, mood="thinking", act="think")],
          props=[dict(kind="phone", x=.62, y=.48, s=1.2, label="market news"), dict(kind="arrow_down", x=.82, y=.42, s=1.0, color=R), dict(kind="arrow_up", x=.9, y=.58, s=1.0, color=G)]),
     "Excuse number three. I'll wait for the market to drop, and then buy. It sounds smart. But even professional investors struggle to time the market consistently. While Sam waits for the perfect moment, the market often climbs higher, and Sam waits some more. Alex has a simpler approach. Invest the same amount every month, whatever the news says. When prices are low, that money buys more. When prices are high, it buys less. Over time, it averages out. This is called dollar cost averaging."),
    (dict(type="big", text="Time IN the market > timing the market", sub="consistency beats cleverness", color=B),
     "There's an old saying among investors. Time in the market beats timing the market. Consistency beats cleverness. Alex isn't smarter than Sam. Alex is just more consistent."),
    (dict(type="stage", head="The real enemy: your own brain", figs=[dict(who="sam", x=.5, mood="shocked", act="shock", say="SELL!!")]),
     "And honestly, the biggest risk for most investors isn't the market at all. It's their own emotions. Fear makes people sell when prices crash. Greed makes people chase whatever went up last year. The best investors are often the ones who set up a sensible plan, automate it, and then stop looking at it every day."),
    # ------------------------------------------------------------ CH7
    (dict(type="chapter", n=7, title="The Simple Plan"),
     "Chapter seven. The simple plan."),
    (dict(type="stage", head="It's not too late, Sam", figs=[
        dict(who="sam", x=.35, mood="thinking", act="think"), dict(who="alex", x=.65, mood="happy", act="point", say="Start today!")]),
     "So what about Sam? Is it too late? No. It is never too late to stop the leak and start compounding. Sam just needs a plan. And here it is, step by step."),
    (dict(type="bullets", title="The plan", icon="num", items=[
        "Track spending for one month", "Build a starter emergency fund", "Kill high-interest debt",
        "Pay yourself first, automatically", "Invest in low-cost index funds", "Save half of every raise"]),
     "Step one. Track your spending for one month. Just look. Find the holes in the bucket. Step two. Build a small starter emergency fund, even one thousand dollars, so the next surprise doesn't go on a credit card. Step three. Attack high interest debt, starting with the highest rate. Step four. Pay yourself first. Set up an automatic transfer on payday. Step five. Invest for the long term in broad, low cost index funds, and leave them alone. Step six. Every time you get a raise, save at least half of it."),
    (dict(type="pie", title="A simple starting budget: 50 / 30 / 20", items=[
        ["needs", 50, B], ["wants", 30, Y], ["savings & debt payoff", 20, G]]),
     "If you want a simple starting point, try the fifty thirty twenty rule. Fifty percent of your take home pay for needs, like housing, food, and transport. Thirty percent for wants, the fun stuff. And twenty percent for savings and paying off debt. It's not perfect for everyone, but it's a great first framework."),
    (dict(type="stage", head="Small steps, big results", figs=[dict(who="sam", x=.3, mood="happy", act="push")],
          props=[dict(kind="snowball", x=.62, y=.62, s=.8, grow=True)]),
     "And Sam starts. Small at first. Cancels a few subscriptions nobody was using. Pays off the credit card. Starts investing two hundred dollars a month, then three hundred, then more. It's not dramatic. It's not exciting. But the snowball has started rolling."),
    (dict(type="big", text="Spend less than you earn. Invest the difference. Wait.", sub="That's it. That's the whole secret.", color=G),
     "Because in the end, the money trap isn't about how much you earn. It's about three simple things. Spend less than you earn. Invest the difference. And give it time. That's it. That's the whole secret. It's simple. It's just not easy."),
    (dict(type="stage", head="Thanks for watching!", figs=[
        dict(who="sam", x=.35, mood="happy", act="wave"), dict(who="alex", x=.65, mood="happy", act="wave")], fx="coins_rain"),
     "Sam and Alex will be back with more money lessons. If this video helped you, subscribe, and share it with a friend who keeps saying they'll start saving next month. Thanks for watching, and see you in the next one."),
]
