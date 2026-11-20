// Motivational copy for set feedback, exercise insight and other moments.
// Placeholders in {braces} are filled by Motivation.fill(). The same line is never shown twice in a row.
const Motivation = (() => {
  const bank = {
    moreWeight: {
      emoji: ['🦍', '💪', '🔥', '🚀', '⚡'],
      titles: ['Zwaarder dan vorige keer!', 'Sterker geworden!', 'Nieuw niveau!', 'Dat voelt zwaarder, hè?', 'De jungle beeft!', 'Plus {diff} kg!'],
      lines: [
        'Je tilt {diff} kg meer dan vorige keer. Zo word je een echte Zilverrug!',
        'Meer gewicht, meer gorilla. Hou dit tempo vast!',
        '{diff} kg erbij. De jij van vorige keer zou hier jaloers op zijn.',
        'Spieren groeien niet van wachten, maar van dit. Goed gedaan!',
        'De halterschijven trillen van angst. Ga zo door!',
        'Progressive overload in het wild gespot. Mooi!',
        'De jij van vorige keer kijkt vol bewondering toe.',
        'Elke kilo erbij is een stap richting King Kong!',
        'Dit is precies hoe je groeit. Stap voor stap, kilo voor kilo.',
      ],
    },
    moreReps: {
      emoji: ['🦍', '💥', '🔥', '🎯'],
      titles: ['Meer reps dan vorige keer!', 'Sterker op hetzelfde gewicht!', 'Extra herhalingen!', 'Plus {diff} rep(s)!'],
      lines: [
        '{diff} rep(s) meer dan vorige keer. Binnenkort mag er een schijfje bij!',
        'Zelfde gewicht, meer herhalingen. Zo wordt het gewicht snel te licht.',
        'Je uithouding groeit mee met je kracht. Mooi werk!',
        'Meer reps is ook vooruitgang. Wie telt er nog kilo\'s?',
        'Dit gewicht begint zijn meester te herkennen.',
        'De jungle is van jou, ook met meer reps!',
        'Als je dit volhoudt, mag je volgende keer zwaarder.',
      ],
    },
    same: {
      emoji: ['✅', '🦍', '🧱', '👌'],
      titles: ['Even sterk als vorige keer', 'Stabiel als een Zilverrug', 'Consistent!', 'Zelfde niveau, solide set'],
      lines: [
        'Hetzelfde als vorige keer. Probeer een rep extra als je kunt!',
        'Consistentie bouwt de sterkste gorilla\'s. Goed bezig!',
        'Stevig als een boomstam. Volgende keer: een extra rep?',
        'Je houdt je niveau vast, en dat is al knap.',
        'Een solide set. Pak er gerust een extra rep bij.',
        'Zelfde kracht, steeds beter techniek. Dat telt ook!',
      ],
    },
    lessReps: {
      emoji: ['🦍', '🌿', '💚'],
      titles: ['Een rustigere set', 'Geen paniek, maat', 'Telt gewoon mee!'],
      lines: [
        'Een rep minder dan vorige keer? Zo\'n dag heeft iedereen. Het gaat om de lange termijn.',
        'Zelfs een Zilverrug heeft rustigere dagen. Jij bent er, dat is het belangrijkste.',
        'Minder reps, maar je kwam wel opdagen. Dat is wat telt!',
        'Volgende set weer vol gas. Je kunt dit.',
        'Elke set is een stapje, ook de moeilijke.',
      ],
    },
    lessWeight: {
      emoji: ['🦍', '🌿', '💚'],
      titles: ['Lichter dan vorige keer', 'Rustig aan is ook een plan', 'Techniek boven ego'],
      lines: [
        'Lichter vandaag? Slim luisteren naar je lichaam is ook kracht.',
        'Soms is een stapje terug de beste aanloop. Volgende keer weer erboven!',
        'Techniek eerst, kilo\'s komen vanzelf. Goed bezig!',
        'Een lichtere dag, maar je staat wel in de gym. Respect.',
        'Even terugschakelen, dan weer opschalen. Zo werkt de jungle.',
      ],
    },
    noPrev: {
      emoji: ['🦍', '🌱', '✅', '💪'],
      titles: ['Set opgeslagen!', 'Weer een set erbij', 'Lekker bezig!', 'In de boeken!'],
      lines: [
        'Elke set is een steentje in je jungle-tempel.',
        'Lekker bezig maat, de jungle is van jou!',
        'Opgeslagen. Nu die volgende set nog.',
        'Dit is een nieuw referentiepunt. Volgende keer verslaan we het!',
        'Zo bouw je data op waar je later trots op bent.',
        'Sets stapelen zich op. Net als je spiermassa.',
        'Een set dichter bij King Kong.',
      ],
    },
    pr: {
      emoji: ['🏆', '👑', '🔥', '⚡'],
      titles: ['NIEUW PR!', 'Persoonlijk record!', 'Je breekt je eigen record!', 'Legendarisch!'],
      lines: [
        'Dit is je zwaarste set ooit op deze oefening. De jungle buigt voor je!',
        'Een nieuw record! Vandaag schrijf je geschiedenis.',
        'De oude jij kijkt omhoog naar de nieuwe jij. Wat een set!',
        'Dit gaat de Wall of Fame in. Mooi werk, Zilverrug!',
        'PR! Beuk op je borst, je hebt het verdiend.',
      ],
    },
    exerciseDone: {
      emoji: ['✅', '🦍', '🏁'],
      titles: ['Oefening afgerond!', 'Klaar met deze!', 'Dat zit erop!'],
      lines: [
        'Je hebt evenveel sets als vorige keer gedaan. Op naar de volgende oefening!',
        'Goed afgewerkt. Tijd voor de volgende uitdaging.',
        'Alle sets erop. Even drinken en dan weer verder!',
        'Netjes afgemaakt. De jungle wacht, volgende oefening!',
      ],
    },
    // Exercise insight (shown when an exercise is selected)
    stagnation4: {
      emoji: ['⚠️', '🥶'],
      titles: ['Je zit vast!'],
      lines: [
        'Je staat al {n} sessies op rij vast op {w} kg. Tijd om de jungle in te duiken: probeer een extra rep of een klein schijfje erbij!',
        '{n} sessies met {w} kg. Zo wordt je nooit King Kong! Durf een stapje zwaarder.',
        '{n} keer hetzelfde gewicht ({w} kg). Je lichaam is eraan gewend, geef het iets nieuws!',
      ],
    },
    stagnation3: {
      emoji: ['⚠️', '🤔'],
      titles: ['Drie keer hetzelfde'],
      lines: [
        'Je staat al {n} sessies op rij op {w} kg. Zo wordt je nooit King Kong!',
        '{n} sessies op {w} kg. Probeer vandaag meer reps of een klein stapje omhoog.',
        'Tijd voor een uitdaging: {w} kg is inmiddels je comfortzone geworden.',
      ],
    },
    stagnation2: {
      emoji: ['🦍', '🎯'],
      titles: ['Stabiel, maar durf meer'],
      lines: [
        'Twee keer op rij {w} kg. Probeer vandaag een extra rep te halen!',
        'Je zit stevig op {w} kg. Eén rep meer en je bent weer in beweging.',
        '{w} kg gaat goed. Klaar voor een uitdaging?',
      ],
    },
    climbing: {
      emoji: ['🚀', '🔥', '🦍'],
      titles: ['Je zit in een goede flow!'],
      lines: [
        'Je bent al {n} sessies op rij zwaarder gegaan. Lekker bezig maat, de jungle is van jou!',
        '{n} sessies op rij vooruitgang. Dit is hoe een Zilverrug wordt geboren!',
        'Sterker, sterker, sterker. Hou dit ritme vast!',
      ],
    },
    up: {
      emoji: ['💪', '🦍'],
      titles: ['Laatste keer vooruitgang'],
      lines: [
        'Vorige keer ging je omhoog naar {w} kg. Probeer dat vandaag te bevestigen!',
        'Je laatste sessie was sterk ({w} kg). Maak het vandaag nog beter!',
      ],
    },
    down: {
      emoji: ['🌿', '🦍'],
      titles: ['Een stapje terug'],
      lines: [
        'Vorige keer was het wat lichter. Vandaag opnieuw aanvallen?',
        'Na een rustige sessie komt een sterke. Vandaag jouw dag?',
      ],
    },
    same1: {
      emoji: ['🦍'],
      titles: ['Klaar voor de volgende stap?'],
      lines: [
        'Je laatste twee sessies waren even zwaar. Een extra rep maakt het verschil!',
        'Je hebt een mooi vast niveau. Tijd om er een schepje bovenop te doen!',
      ],
    },
    fresh: {
      emoji: ['🌱', '🦍'],
      titles: ['Eerste keer op deze oefening'],
      lines: [
        'Nog geen eerdere sessies. Vandaag leg je de basis voor je jungle-imperium!',
        'Een nieuwe oefening, een nieuw avontuur. Begin gerust voorzichtig.',
        'Dit wordt je referentie. Volgende keer verslaan we het!',
      ],
    },
    comeback: {
      emoji: ['👋', '🦍'],
      titles: ['Welkom terug!'],
      lines: [
        'Het is {days} dagen geleden. Start rustig en bouw weer op, de spieren onthouden alles.',
        '{days} dagen pauze, maar de gorilla is terug. Neem de eerste set rustig.',
      ],
    },
    fine: {
      emoji: ['🦍', '💪', '🌴'],
      titles: ['Lekker bezig!', 'Klaar voor actie!', 'De jungle roept!'],
      lines: [
        'Lekker bezig maat, de jungle is van jou!',
        'Laatste keer {w} kg. Kun je dat verbeteren?',
        'Focus, ademhaling, techniek. De rest volgt vanzelf.',
        'Een goede warming-up is het halve werk. Daarna: vol gas!',
        'Elke rep telt. Maak er vandaag eentje meer.',
        'Gorilla\'s worden niet geboren, die worden gebouwd. Set voor set.',
      ],
    },
    timerDone: {
      emoji: ['⏱️'],
      titles: ['Rust voorbij!'],
      lines: ['Volgende set, gorilla!', 'Tijd om weer te knallen!', 'De halter wacht op je.', 'Uitgerust? Dan nu doorpakken!'],
    },
    cardio: {
      emoji: ['🔥', '🏃', '❤️'],
      titles: ['Cardio opgeslagen!', 'Conditie omhoog!', 'Zweet is vet dat huilt'],
      lines: [
        'Goed gedaan! Je hart dankt je later.',
        'Elke minuut telt. Je bouwt een motor van een gorilla.',
        'Cardio is het fundament van een sterke gorilla. Mooi bezig!',
        'Weer een stap richting een fitter jij!',
      ],
    },
    weightDown: {
      emoji: ['📉', '🦍'],
      titles: ['Je gewicht is gedaald!'],
      lines: ['{diff} kg lichter dan de vorige meting. De jungle ziet het resultaat!', 'Mooi! Elke kilo minder is een stap naar je doel.'],
    },
    weightUp: {
      emoji: ['⚖️', '🦍'],
      titles: ['Gewicht opgeslagen'],
      lines: ['Schommelingen horen erbij. Kijk naar de trend, niet naar de dag.', 'Een weging is een momentopname. Houd het grote plaatje in de gaten.'],
    },
    weightSame: {
      emoji: ['⚖️'],
      titles: ['Gewicht opgeslagen'],
      lines: ['Stabiel gebleven. Blijf consequent, de trend maakt het verschil.', 'Meten is weten. Mooi dat je het bijhoudt!'],
    },
  };

  const lastIndex = {};

  function randomIndex(key, length) {
    if (length < 2) return 0;
    let index;
    do { index = Math.floor(Math.random() * length); } while (index === lastIndex[key]);
    lastIndex[key] = index;
    return index;
  }

  function fill(template, vars = {}) {
    return template.replace(/\{(\w+)\}/g, (_, key) => (vars[key] ?? ''));
  }

  function pick(category, vars = {}) {
    const group = bank[category] || bank.noPrev;
    return {
      emoji: group.emoji[randomIndex(`${category}:e`, group.emoji.length)],
      title: fill(group.titles[randomIndex(`${category}:t`, group.titles.length)], vars),
      line: fill(group.lines[randomIndex(`${category}:l`, group.lines.length)], vars),
    };
  }

  const kg = value => (Math.round(value * 100) / 100).toLocaleString('nl-NL');

  // Compares the set that was just saved with the same set number of the previous session.
  function setFeedback({ weight, reps, previous, isPr, setNr, previousSetCount }) {
    if (isPr) return { kind: 'pr', ...pick('pr') };
    const real = previous && !previous.is_estimated && previous.weight != null && weight != null;
    let kind = 'noPrev';
    const vars = {};
    if (real) {
      const heavier = weight - previous.weight;
      if (heavier > 0.01) { kind = 'moreWeight'; vars.diff = kg(heavier); }
      else if (heavier < -0.01) kind = 'lessWeight';
      else if (reps != null && previous.reps != null) {
        if (reps > previous.reps) { kind = 'moreReps'; vars.diff = reps - previous.reps; }
        else if (reps < previous.reps) kind = 'lessReps';
        else kind = 'same';
      } else kind = 'same';
    }
    if (kind === 'noPrev' && previousSetCount && setNr >= previousSetCount) kind = 'exerciseDone';
    return { kind, ...pick(kind, vars) };
  }

  // Picks the headline for the card shown when an exercise is opened.
  function exerciseInsight(insight) {
    const sessions = insight?.sessions || [];
    if (!sessions.length) return { kind: 'fresh', ...pick('fresh'), chips: [] };
    const latest = sessions[0];
    const vars = { n: insight.stagnation, w: kg(latest.max_weight), days: insight.days_since };
    let kind = 'fine';
    if (insight.stagnation >= 4) kind = 'stagnation4';
    else if (insight.stagnation === 3) kind = 'stagnation3';
    else if (insight.stagnation === 2) kind = 'stagnation2';
    else if (insight.climbing >= 2) { kind = 'climbing'; vars.n = insight.climbing; }
    else if (insight.days_since >= 14) kind = 'comeback';
    else if (insight.trend === 'up') kind = 'up';
    else if (insight.trend === 'down') kind = 'down';
    else if (insight.trend === 'same') kind = 'same1';
    const chips = [`Laatst ${kg(latest.max_weight)} kg${latest.max_reps ? ` × ${latest.max_reps}` : ''}`];
    if (insight.best_weight != null) chips.push(`Beste ${kg(insight.best_weight)} kg`);
    if (insight.stagnation >= 2) chips.push(`${insight.stagnation}× zelfde gewicht`);
    else if (insight.climbing >= 2) chips.push(`${insight.climbing}× omhoog`);
    return { kind, ...pick(kind, vars), chips };
  }

  function weightFeedback(previousKg, currentKg) {
    if (previousKg == null) return pick('weightSame');
    const diff = Math.round((previousKg - currentKg) * 10) / 10;
    if (diff > 0.05) return pick('weightDown', { diff: kg(diff) });
    return pick(diff < -0.05 ? 'weightUp' : 'weightSame');
  }

  return { pick, fill, setFeedback, exerciseInsight, weightFeedback };
})();
