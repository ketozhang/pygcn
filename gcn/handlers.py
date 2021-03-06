# Copyright (C) 2014-2018  Leo Singer
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
"""
Payload handlers.
"""

#######################################
###Newly addded########################
import sys
import os
import gcn.voeventparser as voeventparser
from astrosql import AstroSQL
from astrosql.sqlconnector import connect
from gcn.gcnfollowup import *
db = AstroSQL(database='observation')
#######################################

import functools
import logging
from six.moves.urllib.parse import quote_plus

__all__ = ('get_notice_type', 'include_notice_types', 'exclude_notice_types',
           'archive', 'followupkait')


def get_notice_type(root):
    return int(root.find("./What/Param[@name='Packet_Type']").attrib['value'])


def include_notice_types(*notice_types):
    """Process only VOEvents whose integer GCN packet types are in
    `notice_types`. Should be used as a decorator, as in:

        import gcn.handlers
        import gcn.notice_types as n

        @gcn.handlers.include_notice_types(n.FERMI_GBM_GND_POS,
                                           n.FERMI_GBM_FIN_POS)
        def handle(payload, root):
            print('Got notice of type FERMI_GBM_GND_POS or FERMI_GBM_FIN_POS')
    """
    notice_types = frozenset(notice_types)

    def decorate(handler):
        @functools.wraps(handler)
        def handle(payload, root):
            if get_notice_type(root) in notice_types:
                handler(payload, root)
        return handle
    return decorate


def exclude_notice_types(*notice_types):
    """Process only VOEvents whose integer GCN packet types are not in
    `notice_types`. Should be used as a decorator, as in:

        import gcn.handlers
        import gcn.notice_types as n

        @gcn.handlers.exclude_notice_types(n.FERMI_GBM_GND_POS,
                                           n.FERMI_GBM_FIN_POS)
        def handle(payload, root):
            print('Got notice not of type FERMI_GBM_GND_POS '
                  'or FERMI_GBM_FIN_POS')
    """
    notice_types = frozenset(notice_types)

    def decorate(handler):
        @functools.wraps(handler)
        def handle(payload, root):
            if get_notice_type(root) not in notice_types:
                handler(payload, root)
        return handle
    return decorate

def archive(payload, root):
    """Payload handler that archives VOEvent messages as files in the current
    working directory. The filename is a URL-escaped version of the messages'
    IVORN."""
    ivorn = root.attrib['ivorn']
    filename = quote_plus(ivorn)
    with open(filename, 'wb') as f:
        f.write(payload)
    logging.getLogger('gcn.handlers.archive').info("archived %s", ivorn)

#######################################
###Newly addded########################
def savetofile(payload, root):
    ivorn = root.attrib['ivorn']
    archive_path="/media/data12/voevent/archive/"
    from datetime import datetime
    savedir=archive_path+datetime.utcnow().strftime("%Y%m%d")+"/"
    if not os.path.exists(savedir) :
        os.makedirs(savedir,exist_ok=True)
        command="chgrp -R flipper "+savedir
        print(command)
        os.system(command)
        command="chmod 770 "+savedir
        print(command)
        os.system(command)
    filename = savedir+quote_plus(ivorn)
    with open(filename, 'wb') as f:
        f.write(payload)
    logging.getLogger('gcn.handlers.archive').info("archived %s", filename)

def sendoutemail(payload, root):
    ##send out email
    tmpfile='/media/data12/voevent/emailtmp/emailtmp.xml'
    with open(tmpfile, 'wb') as f:
        f.write(payload)
    logging.getLogger('gcn.handlers.sendoutemail').info("saved to tmp file %s", tmpfile)
    command="voeventalertemail "+tmpfile
    os.system(command)

def addtriggersintodatabase(data):
    table1 = db.get_table("voevents")

    query = table1.insert(data)
    query.execute()

def addgalaxyintodatabase(data,galaxy):
    #add 1500 galaxies at most into database
    if len(galaxy) > 1500 :
        print('galaxy is longer than 1500 items, truncate to 1500')
        galaxy=galaxy[0:1500]
    table2 = db.get_table("voevents_galaxy")
    print('Adding galaxyies into voeventsgalaxy table')
    g=galaxy.to_pandas().astype(object)
    g['TriggerNumber'] = data['TriggerNumber']
    g['TriggerSequence'] = data['TriggerSequence']
    #g['Kait_observable'] = 'N'
    g['Kait_observed'] = 'N'
    #g['Time_observed'] = None
    #g['Limit_mag'] = 0
    #g['Comment'] = None
    data = g.to_dict('records')
    query = table2.insert(data)
    query.execute()
    

def radecfollowups(ra,dec,error,peakz=0.1,triggerid=0,triggersequence=0):
    print("Do real radecfollowup observations")
    print("Ra:",ra," Dec:",dec,"Error:",error, "peakz:",peakz)
    #prepare the directory
    if triggerid == 0:
        outputdir='/media/data12/voevent/rqs/0/'
        os.makedirs(outputdir,exist_ok=True)
        olddir=outputdir+"{:d}".format(triggersequence)
        os.makedirs(olddir,exist_ok=True)
        command="mv -f "+outputdir+"*  "+olddir
        print(command)
        #os.system(command)
        outputrqsbase=0
        runcommand=True
    else :
        triggerdir='/media/data12/voevent/rqs/'+"{:d}".format(triggerid)+"/"
        if not os.path.exists(triggerdir) :
            os.makedirs(triggerdir,exist_ok=True)
            outputdir=triggerdir+"{:d}".format(triggersequence)+"/"
            os.makedirs(outputdir,exist_ok=True)
            outputrqsbase=0
            runcommand=True
        else :
            outputdir=triggerdir+"{:d}".format(triggersequence)+"/"
            ##findout how many folders already, namely how many sequence
            outputrqsbase=len(next(os.walk(triggerdir))[1])
            print('outputrqsbase is: ',outputrqsbase)
            ##create the new sequence folder
            os.makedirs(outputdir,exist_ok=True)
            runcommand=False
    g1=select_gladegalaxy_accordingto_location_radecpeakz(ra,dec,error,peakz)
    g2=select_gladegalaxy_accordingto_luminosity(g1)
    g3=select_gladegalaxy_accordingto_detectionlimit(g2)
    ##also save the galaxt in outputdir as a cvs file
    outputcvsfile=outputdir+"{:d}".format(triggerid)+'_'+"{:d}".format(triggersequence)+'.cvs'
    g3.write(outputcvsfile,format='ascii.csv')

    outputhourbase=24
    gen_kait_rqs_from_table(g3,outputhourbase=outputhourbase,outputrqsbase=outputrqsbase, outputdir=outputdir, runcommand=runcommand)
    return g3

def gwskymapfollowups(skymaplinkorfile,triggerid=0,triggersequence=0):
    print("Do real gwskymapfollowup observations")
    #prepare the directory
    if triggerid == 0:
        outputdir='/media/data12/voevent/rqs/0/'
        os.makedirs(outputdir,exist_ok=True)
        olddir=outputdir+"{:d}".format(triggersequence)
        os.makedirs(olddir,exist_ok=True)
        command="mv -f "+outputdir+"*  "+olddir
        print(command)
        #os.system(command)
        outputrqsbase=0
    else :
        triggerdir='/media/data12/voevent/rqs/'+"{:d}".format(triggerid)+"/"
        if not os.path.exists(triggerdir) :
            os.makedirs(triggerdir,exist_ok=True)
            outputdir=triggerdir+"{:d}".format(triggersequence)+"/"
            os.makedirs(outputdir,exist_ok=True)
            outputrqsbase=0
            runcommand=True
        else :
            outputdir=triggerdir+"{:d}".format(triggersequence)+"/"
            ##findout how many folders already, namely how many sequence
            outputrqsbase=len(next(os.walk(triggerdir))[1])
            print('outputrqsbase is: ',outputrqsbase)
            ##create the new sequence folder
            os.makedirs(outputdir,exist_ok=True)
            runcommand=False
    print(skymaplinkorfile)
    ##if it is a link, need to download to local first
    os.chdir(outputdir)
    if skymaplinkorfile[0:3] == "http" :
        os.system('wget '+skymaplinkorfile)
        skymap=skymaplinkorfile.split('/')[-1]
    else :
        skymap=skymaplinkorfile
    print("skymap file is : "+skymaplinkorfile)
    if not os.path.isfile(skymap) :
        print('skymap file does not exist, please check!!!')
        return None
    g3=select_gladegalaxy_accordingto_location_gw(skymap)
    ##also save the galaxt in outputdir as a cvs file
    outputcvsfile=outputdir+"{:d}".format(triggerid)+'_'+"{:d}".format(triggersequence)+'.cvs'
    g3.write(outputcvsfile,format='ascii.csv')

    outputhourbase=48
    gen_kait_rqs_from_table(g3,outputhourbase=outputhourbase,outputrqsbase=outputrqsbase, outputdir=outputdir, runcommand=runcommand)
    return g3

def followupkait(payload, root):
    """This is for KAIT follow up procedures"""
    ivorn = root.attrib['ivorn']
    print('Received: ',ivorn)

    ##here is the real processing
    import gcn.notice_types as n

    ##These notices we need to save
    notice_types = frozenset([n.FERMI_GBM_GND_POS,
                              n.FERMI_GBM_FLT_POS,
                              n.FERMI_GBM_FIN_POS,
                              n.SWIFT_BAT_GRB_POS_ACK,
                              n.AGILE_GRB_WAKEUP,
                              n.AGILE_GRB_GROUND,
                              n.AGILE_GRB_REFINED,
                              n.FERMI_LAT_POS_INI,
                              n.FERMI_LAT_GND,
                              n.MAXI_UNKNOWN,
                             #n.MAXI_TEST,
                              n.LVC_PRELIM,
                              n.LVC_INITIAL,
                              n.LVC_UPDATE,
                              n.LVC_TEST,
                              n.LVC_CNTRPART,
                              n.AMON_ICECUBE_COINC,
                              n.AMON_ICECUBE_HESE,
                              n.CALET_GBM_FLT_LC,
                              n.CALET_GBM_GND_LC,
                              n.LVC_SUPER_PRELIM,
                              n.LVC_SUPER_INITIAL,
                              n.LVC_SUPER_UPDATE,
                              n.GWHEN_COINC,
                              n.AMON_ICECUBE_EHE])

    if get_notice_type(root) in notice_types:
        savetofile(payload, root)

    ##These notices we need to sendout email alert
    notice_types = frozenset([n.FERMI_GBM_GND_POS,
                              n.FERMI_GBM_FLT_POS,
                              n.FERMI_GBM_FIN_POS,
                              n.SWIFT_BAT_GRB_POS_ACK,
                              n.AGILE_GRB_WAKEUP,
                              n.AGILE_GRB_GROUND,
                              n.AGILE_GRB_REFINED,
                              n.FERMI_LAT_POS_INI,
                              n.FERMI_LAT_GND,
                              n.MAXI_UNKNOWN,
                             #n.MAXI_TEST,
                              n.LVC_PRELIM,
                              n.LVC_INITIAL,
                              n.LVC_UPDATE,
                              n.LVC_TEST,
                              n.LVC_CNTRPART,
                              n.AMON_ICECUBE_COINC,
                              n.AMON_ICECUBE_HESE,
                              n.CALET_GBM_FLT_LC,
                              n.CALET_GBM_GND_LC,
                              n.LVC_SUPER_PRELIM,
                              n.LVC_SUPER_INITIAL,
                              n.LVC_SUPER_UPDATE,
                              n.GWHEN_COINC,
                              n.AMON_ICECUBE_EHE])

    if get_notice_type(root) in notice_types:
        sendoutemail(payload, root)

    ##dealing with GBM/MAXI/AMON triggers, all just have ra,dec and error
    notice_types = frozenset([n.FERMI_GBM_GND_POS,
                              n.FERMI_GBM_FLT_POS,
                              n.FERMI_GBM_FIN_POS,
                              n.MAXI_UNKNOWN,
                              n.AMON_ICECUBE_COINC,
                              n.AMON_ICECUBE_HESE,
                              n.AMON_ICECUBE_EHE])
    if get_notice_type(root) in notice_types:
        ##add into database
        data = voeventparser.parse(root)
        addtriggersintodatabase(data)
        if data['Comment'] == 'unknown' or data['Comment'] == 'Short' :
            print('It is a Short or unknown GRB, use peak z=0.1')
            peakz=0.1
        else :
            print('It is a long GRB, use peak z=0.4')
            peakz=0.4
        galaxy=radecfollowups(data['RA'],data['Dec'],data['ErrorRadius'],peakz=peakz,triggerid=data['TriggerNumber'],triggersequence=data['TriggerSequence'])
        addgalaxyintodatabase(data,galaxy)

    ##dealing with LV GW O3 events
    notice_types = frozenset([n.LVC_PRELIM,
                              n.LVC_INITIAL,
                              n.LVC_UPDATE])
    if get_notice_type(root) in notice_types:
        #sendouttxtalert()
        data = voeventparser.parse(root)
        addtriggersintodatabase(data)
        galaxy=gwskymapfollowups(data['Comment'],triggerid=data['TriggerNumber'],triggersequence=data['TriggerSequence'])
        addgalaxyintodatabase(data,galaxy)
