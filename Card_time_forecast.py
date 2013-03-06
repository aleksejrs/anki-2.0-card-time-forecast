#!/usr/bin/python -tt
# -*- coding: utf-8 -*-
# Copyright: Aleksej
# Based on anki.stats from Anki 2.0.5.  Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import time

from numpy import median

from aqt import mw
from aqt.qt import *

from anki.stats import CardStats
from anki.utils import fmtTimeSpan


def aleksejCardStatsReportForForecast(self):
        c = self.card
        fmt = lambda x, **kwargs: fmtTimeSpan(x, short=True, **kwargs)
        self.txt = "<table width=100%>"
        self.addLine(_("Added"), self.date(c.id/1000))
        first = self.col.db.scalar(
            "select min(id) from revlog where cid = ?", c.id)
        last = self.col.db.scalar(
            "select max(id) from revlog where cid = ?", c.id)
        if first:
            self.addLine(_("First Review"), self.date(first/1000))
            self.addLine(_("Latest Review"), self.date(last/1000))
        if c.type in (1,2):
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
            if c.factor == 1300:
                ease_str = '<i>%s</i>' % ease_str


            all_times = self.col.db.list(
                "select time/1000 from revlog where cid = :id",
                id=c.id)

            cnt = len(all_times)

            if cnt > 4:
                first_factor = self.col.db.list(
                    "select factor from revlog where cid = :id and factor != 0 limit 1",
                    id=c.id)

                # 2500 - 1300 = 1200 = 100%
                # 2500 - 2500 = 0 = 0%
                # 2500 - 2600 = -100 = 0%
                if len(first_factor) > 0:
                    medium_ease = (2500 + first_factor[0]) / 2
                else:
                    medium_ease = 2500

                if c.factor < medium_ease:
                    lowest_ease_possible = 1300
                    if medium_ease == lowest_ease_possible:
                        medium_ease += 1
                    ease_red_perc = 100 * (medium_ease - c.factor) / (medium_ease - 1300)
                    ease_green_perc = 0
                elif c.factor > medium_ease:
                    highest_ease_possible = 3560
                    if medium_ease == highest_ease_possible:
                        medium_ease -= 1
                    ease_green_perc = 100 * (c.factor - medium_ease) / (highest_ease_possible - medium_ease)
                    ease_red_perc = 0
                else:
                    ease_green_perc = ease_red_perc = 0

                if ease_green_perc > 100:
                    ease_green_perc = 100

                ease_str = '<span style="color: rgb({0}%, {1}%, 0%)">{2}</span>'.format(
                        ease_red_perc, ease_green_perc, ease_str)

            self.addLine(_("Ease"), ease_str)
            self.addLine(_("Reviews"), "%d" % c.reps)
            self.addLine(_("Lapses"), "%d" % c.lapses)
            
            if cnt:

                time_avg, time_median = time_avg_and_median(all_times)


                def repstime_this(days):
                    return repstime(days=days, time_avg=time_avg,
                                    time_median=time_median, ivl=c.ivl,
                                    factor=c.factor)

                def addCardForecast(caption, days):
                    if not (c.ivl > 0):
                        return  # in-learning cards not supported
#                    caption = fmt(days * 86400)

                    if c.odid and c.type == 2:
                        deck_name = self.col.decks.name(c.odid)
                    else:
                        deck_name = self.col.decks.name(c.did)

                    time_str = repstime_s(days=days, factor=c.factor,
                            time_avg=time_avg, time_median=time_median,
                            ivl=c.ivl, cardStatsObject=self)

                    years = days / 365.0



                    if 'Anki' in deck_name:
                        # Anki may be very different in 10 years.
                        if years >= 10:
                            return

                    if 'Python' in deck_name:
                        if years >= 15:
                            return

                    if 'People' in deck_name:
                        if years > 15:
                            return

                    # Firefox may be very different in 10 years.
                    if 'Fx' in deck_name and 'eyboard' in deck_name:
                        if years >= 10:
                            return
                        elif years == 5:
                            addRLine(self, caption, "<b>" + time_str + "</b>")
                            return

                    if 'Capitals' in deck_name:
                        if years < 3:
                            return


                    if 'koordinatoj' in deck_name:
                        if years < 5:
                            return


                    if u'история' in deck_name:
                        if years < 3:
                            return

                    if 'Math' in deck_name and not u'история' in deck_name:
                        if years < 5:
                            return


                    if years == 15:
                        caption = '<span style="color: green">%s</span>' % caption
                    elif years == 40:
                        caption = '<small>%s</small>' % caption



                    addRLine(self, caption, time_str)


                if abs(1 - time_avg / time_median) < 0.04:
                    avgAndMedTimeLineText = self.time( (time_median + time_avg) / 2)
                else:
                    avgAndMedTimeLineText = self.time(time_avg) + self.time(time_median)
                self.addLine(_("Avg,Med time"), avgAndMedTimeLineText)

                self.addLine(_("Total Time"), self.time(sum(all_times)))
#                self.addLine(_("All times"), all_times)

                if cnt >= 3 or (cnt >= 2 and c.ivl > 100):

                    forecast_list = [('1 Y', 365 * 1),
                                     ('5 Y', 365 * 5),
                                     ('10 Y', 365 * 10),
                                     ('15 Y', 365 * 15)]
#                                     ('40 Y', 365 * 40)]

                    forecast_captions, forecast_days = zip(*forecast_list)
                    forecast_captions, forecast_days = list(forecast_captions), list(forecast_days)
                    forecast_days.append(365 * 100)

                    # cards which need less than 8 seconds to learn are not
                    # worth deleting
                    for i in range(len(forecast_list)):
                        nextIsNotVerySmall = repstime_this(forecast_days[i + 1]) > 8
                        nextIsBigger = repstime_this(forecast_days[i]) < repstime_this(forecast_days[i + 1])

                        if nextIsNotVerySmall and nextIsBigger:
                            addCardForecast(forecast_captions[i], forecast_days[i])


        elif c.queue == 0:
            self.addLine(_("Position"), c.due)
        self.addLine(_("Card Type"), c.template()['name'])
        self.addLine(_("Note Type"), c.model()['name'])
        self.addLine(_("Deck"), self.col.decks.name(c.did))
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

    for reps in range(1, 999):

        ivl *= ease
        total_ivl += ivl

        yield (reps, total_ivl)


def time_avg_and_median(all_times):
    """Takes duration of every review and returns average and median.
    
    Durations are in seconds.
    """

    if len(all_times) < 7:
        timeList = all_times
    else:
        oldest_count = len(all_times) // 5
        timeList = all_times[oldest_count - 1:]

    time_avg = sum(timeList) / float(len(timeList))
    time_median = median(timeList)

    return time_avg, time_median


def timeForRepsAndAverageTimes(reps, time_avg, time_median):
    return reps * (time_avg + time_median) / 2


def repstime(days, time_avg, time_median, ivl, factor):
    """Returns time needed to know this card for days days since some??? answer."""
    reps = repsForIvlFactorAndMaximum(ivl=ivl, factor=factor, days=days)
    return timeForRepsAndAverageTimes(reps, time_avg, time_median)




def repstime_s(days, factor, time_avg, time_median, ivl, cardStatsObject):
    """Returns time as "1m 30s"
    """
    time_num = repstime(days=days, time_avg=time_avg, time_median=time_median,
            ivl=ivl, factor=factor)
    timestr = cardStatsObject.time(time_num)
    if factor == 1300:
        fmt_time = '>=%s' % timestr
    else:
        fmt_time = '%s' % timestr

    if (days > (365 * 3) and time_num < 10):
        fmt_time = '<span style="color: green">%s</span>' % fmt_time
    elif days > (365 * 40):
        fmt_time = '<small>%s</small>' % fmt_time

    if time_num >= 120:
        fmt_time = '<i>%s</i>' % fmt_time

    return fmt_time


def repsForIvlFactorAndMaximum(ivl, factor, days):
    # I guess this is currently just a proxy because I want to adapt it
    # for cards due in the future.  Then it will substract the "due in"
    # time from the "days".
    return reps_for_total_ivl(ivl=ivl, factor=factor, max_total_ivl=days)


CardStats.report = aleksejCardStatsReportForForecast

