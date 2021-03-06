#!/usr/bin/python -tt
# -*- coding: utf-8 -*-
# Copyright: Aleksej
# Based on anki.stats from Anki 2.0.15 (the report function by Damien Elmes
# <anki@ichi2.net>).
# License: GNU Affero General Public License, version 3 only; http://www.gnu.org/licenses/agpl.html

import time

from aqt.qt import *

from anki.stats import CardStats
from anki.utils import fmtTimeSpan


# 1300 is the minimum ease, the card may actually be harder.
lowest_ease_possible = 1300

# For the forecast of how many Anki days of your life the reviews will take.
# Used for more realistic forecasting in minutes
# Include only the time you can dedicate to the kind of reviews this add-on
# measures (not Incremental reading).
avg_total_review_mins_per_day = 31.5

# All time. Gives bigger numbers, but some of the time will always be used for
# sleep anyway.
#hours_in_day = 24.0
# Only the awake time. Unstable though.
# "Study screen time forecast" will use that to show the amount in days, but
# the amount of days will be the same as with 24.0 (everything is based on
# the ratio of avg_total_review_mins_per_day to hours_in_day).
hours_in_day = 15.0


def percFromBaseToExtreme(value, base, extreme):
    """Shows, in %, where value is on the way from base to extreme.

    Used for coloring numbers.
    """
    # Examples:
    # base = 2500, extreme = 1300; 2500 - 1300 = 1200.
    # value 1300: (2500 - 1300) / 1200 = 100%
    # value 1900: (2500 - 1900 = 600) / 1200 = 50%
    # value 2500: (2500 - 2500) / whatever = 0%
    # base = 2500, extreme = 3560, 2500 - 3560 = -1060
    # value 2600: (2500 - 2600 = -100) / 1060 = 9%
    if base == extreme:
        perc = 100
    else:
        perc = 100 * (base - value) / (base - extreme)
        if perc > 100:
            perc = 100

    return perc


def aleksejCardStatsReportForForecast(self):

    # Make Ease number green for easy cards.  Low ease numbers are marked
    # red, so you may want to disable this if it is difficult for you to
    # distinguish red and green.
    opt_use_green_for_ease = True

    c = self.card
    fmt = lambda x, **kwargs: fmtTimeSpan(x, short=True, **kwargs)
    self.txt = '<table width="100%">'
    self.addLine(_("Added"), self.date(c.id/1000))
    first = self.col.db.scalar(
        "select min(id) from revlog where cid = ?", c.id)
    last = self.col.db.scalar(
        "select max(id) from revlog where cid = ?", c.id)
    if first:
        self.addLine(_("First Review"), self.date(first/1000))
        self.addLine(_("Latest Review"), self.date(last/1000))
    if c.type in (1, 2):
        if c.odid or c.queue < 0:
            next = None
        else:
            if c.queue in (2,3):
                next = time.time()+((c.due - self.col.sched.today)*86400)
            else:
                next = c.due
            next = self.date(next)
        if next:
            self.addLine(_("Due"), next)
        if c.queue == 2:
            self.addLine(_("Interval"), fmt(c.ivl * 86400))

        ease_str = '%d%%' % (c.factor / 10.0)
        if c.factor <= lowest_ease_possible:
            ease_str = '<i>%s</i>' % ease_str


        all_times = self.col.db.list(
            "select time/1000 from revlog where cid = :id",
            id=c.id)

        cnt = len(all_times)

        # Making the Ease number red or green.
        if cnt > 4:
            first_factor = self.col.db.list(
                "select factor from revlog where cid = :id and factor != 0 limit 1",
                id=c.id)

            # Account for a custom Starting Ease at the first review.
            if len(first_factor) > 0:
                medium_ease = first_factor[0]
            else:
                medium_ease = 2500

            if c.factor < medium_ease:
                ease_green_perc = 0
                ease_red_perc = percFromBaseToExtreme(
                    c.factor, medium_ease, lowest_ease_possible)
            # If the card is easy, make the number green.
            # XXX: This is not very useful, and may be bad for
            # accessibility (color blindness).  To disable it, change
            # opt_use_green_for_ease above to False.
            elif c.factor > medium_ease and opt_use_green_for_ease:
                # Precision is probably not important here.
                highest_ease_possible = 3560
                ease_red_perc = 0
                ease_green_perc = percFromBaseToExtreme(
                            c.factor, medium_ease, highest_ease_possible)
            else:
                ease_green_perc = ease_red_perc = 0


            ease_str = '<span style="color: rgb({0}%, {1}%, 0%)">{2}</span>'.format(
                ease_red_perc, ease_green_perc, ease_str)

        self.addLine(_("Ease"), ease_str)
        self.addLine(_("Reviews"), "%d" % c.reps)
        self.addLine(_("Lapses"), "%d" % c.lapses)

        if cnt:

            time_avg = get_time_avg(all_times)


            def repstime_this(days):
                return repstime(days=days, time_avg=time_avg,
                                ivl=c.ivl, factor=c.factor)

            def addCardForecast(caption, days):
                if not (c.ivl > 0):
                    return  # in-learning cards not supported
#                caption = fmt(days * 86400)

#                time_num = repstime(
#                    days=days, time_avg=time_avg,
#                    ivl=c.ivl, factor=c.factor)
                time_str = repstime_s(days=days, factor=c.factor,
                                      time_avg=time_avg,
                                      ivl=c.ivl, cardStatsObject=self)

                years = days / 365.0


                if years == 15:
                    caption = ('<span style="color: green">%s</span>' %
                               caption)
                elif years == 40:
                    caption = '<small>%s</small>' % caption


                addRLine(self, caption, time_str)


            self.addLine(_("Avg time"), self.time(time_avg))

            self.addLine(_("Total Time"), self.time(sum(all_times)))
#            self.addLine(_("All times"), all_times)

            if cnt >= 3 or (cnt >= 2 and c.ivl > 100):
                # Account for cards due in the future -- consider the
                # due date the date of the next answer.
                subtract_from_forecast_days = 0
                if c.queue in (2,3) and c.due > self.col.sched.today:
                    subtract_from_forecast_days = (c.due - self.col.sched.today)


#               forecast_list = [('1 Y', 365 * 1),
                forecast_list = [('5 Y', 365 * 5),
                                 ('10 Y', 365 * 10),
                                 ('15 Y', 365 * 15)]
#                                 ('40 Y', 365 * 40)]

                forecast_captions, forecast_days = zip(*forecast_list)
                forecast_captions, forecast_days = list(forecast_captions), list(forecast_days)
                forecast_days.append(365 * 100)

                for i in range(len(forecast_list)):
                    # Show no more than one forecast of 8 seconds or less.
                    nextIsNotVerySmall = repstime_this(forecast_days[i + 1] - subtract_from_forecast_days) > 8
                    # Skip the forecast if the next one is the same.
                    nextIsBigger = (repstime_this(forecast_days[i] - subtract_from_forecast_days) <
                                    repstime_this(forecast_days[i + 1] - subtract_from_forecast_days))

                    if nextIsNotVerySmall and nextIsBigger:
                        addCardForecast(forecast_captions[i], forecast_days[i] -
                                        subtract_from_forecast_days)

    elif c.queue == 0:
        self.addLine(_("Position"), c.due)
    self.addLine(_("Card Type"), c.template()['name'])
    self.addLine(_("Note Type"), c.model()['name'])

    if c.odid and c.type == 2:
        deck_name = u"{0} ({1})".format(
            self.col.decks.name(c.did), self.col.decks.name(c.odid))
    else:
        deck_name = self.col.decks.name(c.did)
    self.addLine(_("Deck"), deck_name)
    self.addLine(_("Note ID"), c.nid)
    self.addLine(_("Card ID"), c.id)
    self.txt += "</table>"
    return self.txt


def addRLine(self, k, v):
    """Add a line with right-aligned caption to a CardStats object"""

    def makeRLine(k, v):
        txt = "<tr><td align=right>"
        txt += "<b>%s</b></td><td>%s</td></tr>" % (k, v)
        return txt

    self.txt += makeRLine(k, v)


def reps_for_total_ivl(ivl, factor, max_total_ivl):
    """Repetitions required to retain during max_total_ivl from now."""

    if ivl == 0:
        return 0

    for (reps, total_ivl) in total_ivls(ivl, factor / 1000.0):

        if total_ivl >= max_total_ivl:
            return reps


def total_ivls(ivl, ease):
    """The total sum of intervals for each number of repetitions.
    
    >>> total_ivls(20, 2.50)[:2]
    [(1, 50), (2, 175), (3, 525)]
    
    """

    total_ivl = 0

    for reps in range(1, 100000):

        ivl *= ease
        total_ivl += ivl

        yield (reps, total_ivl)


def get_time_avg(all_times):
    """Takes duration of almost every review and returns average.
    Skips the oldest reviews if there is enough.

    Durations are in seconds.
    """

    if len(all_times) < 7:
        timeList = all_times
    else:
        oldest_count = len(all_times) // 5
        timeList = all_times[oldest_count - 1:]

    time_avg = sum(timeList) / float(len(timeList))  # much faster than numpy.mean

    return time_avg


def repstime(days, time_avg, ivl, factor):
    """Returns time needed to know this card for days days since next
    answer (for Review cards only).
    """
    if days <= 0:   # forecast requested for before the due date
        return 0
    else:
        reps = reps_for_total_ivl(ivl=ivl, factor=factor, max_total_ivl=days)
        return reps * time_avg


def repstime_s(days, factor, time_avg, ivl, cardStatsObject):
    """Returns time as "1m 30s"
    """
    time_num = repstime(days=days, time_avg=time_avg, ivl=ivl, factor=factor)
    timestr = cardStatsObject.time(time_num)
    if factor <= lowest_ease_possible:
        fmt_time = '>=%s' % timestr
    else:
        fmt_time = '%s' % timestr

    # To make forecast times red if they are big.
    foretime_base = 60
    foretime_max = 330
    foretime_red_perc = foretime_green_perc = 0

    if days > (365 * 3) and time_num < 10:
        foretime_green_perc = 50
    elif days > (365 * 40):
        fmt_time = '<small>%s</small>' % fmt_time
    elif time_num > foretime_base:
        foretime_red_perc = percFromBaseToExtreme(
            time_num, foretime_base, foretime_max)


    if time_num >= 120:
        fmt_time = '<i>%s</i>' % fmt_time

    fmt_time = u'<span style="color: rgb({0}%, {1}%, 0%)">{2}</span>'.format(
        foretime_red_perc, foretime_green_perc, fmt_time)

    return fmt_time

def secOfLifePerReviewSec(avg_total_review_mins_per_day, hours_in_day):
    return hours_in_day * 60 /  avg_total_review_mins_per_day

# The following 2 functions are used in other add-ons only.

def getForecastText(self, c, forecast_days):
    # Returns text forecast for card c in seconds, with "s" added.
    f = getForecast(self, c, forecast_days)
    if f:
        minOfLife = f * secOfLifePerReviewSec(avg_total_review_mins_per_day, hours_in_day) / 60.0
        minOfLifeStr = "{0:.1f}m".format(minOfLife)
#       Minutes based on the ratio of review time to whole day time.
#        return "{}".format(minOfLifeStr)
        # Pure review seconds (default).
        return (str(int(f)) + 's')
    else:
        return ''


def getForecast(self, c, forecast_days):
    # Returns forecast for card c in seconds.
    if not (c.ivl > 0):
        return  # in-learning cards not supported

    all_times = self.col.db.list(
        "select time/1000 from revlog where cid = :id",
        id=c.id)

    cnt = len(all_times)

    if cnt:

        time_avg = get_time_avg(all_times)


        def repstime_this(days):
            return repstime(days=days, time_avg=time_avg, ivl=c.ivl,
                            factor=c.factor)


        if c.queue in (2, 3):
            if c.due > self.col.sched.today:
                forecast_days -= (c.due - self.col.sched.today)

        forecast = repstime_this(forecast_days)
        if forecast:
            return forecast
        else:
            return None




CardStats.report = aleksejCardStatsReportForForecast
