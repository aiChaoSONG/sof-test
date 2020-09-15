#!/bin/bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright(c) 2020 Intel Corporation. All rights reserved.
set -e

##
## Case Name: check-codec-adapter
## Preconditions:
##    require python3-numpy, python3-scipy and python3-matplotlib
##    to be installed, or wavetool.py will not work
## Description:
##    test codec_adapter component in a pipeline
## Case step:
##    1. acquire playback pipeline with codec_adapter component
##    2. generate playback wave file (default 997Hz sine wave)
##    3. play reference wave file through codec_adapter playback pipeline
##       and record it back through the loopback capture pipeline
##    4. verify THD+N value with wavetool.py
## Expect result:
##    1. THD+N should below threshold
## Limitations:
##    This case can only work in nocodec mode, in which SSP loop back is enabled.
##

# source from the relative path of current folder
# shellcheck source=case-lib/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")"/../case-lib/lib.sh

# What we want here is the "$TPLG" string
# shellcheck disable=SC2016
OPT_OPT_lst['t']='tplg'     OPT_DESC_lst['t']='tplg file, default value is env TPLG: $TPLG'
# $TPLG is assigned outside this script as env variable
# shellcheck disable=SC2153
OPT_PARM_lst['t']=1         OPT_VALUE_lst['t']="$TPLG"

OPT_OPT_lst['s']='sof-logger'   OPT_DESC_lst['s']="Open sof-logger trace the data will store at $LOG_ROOT"
OPT_PARM_lst['s']=0             OPT_VALUE_lst['s']=1

OPT_OPT_lst['l']='loop'     OPT_DESC_lst['l']='loop count'
OPT_PARM_lst['l']=1         OPT_VALUE_lst['l']=1

OPT_OPT_lst['d']='duration' OPT_DESC_lst['d']='playback/capture duration in second'
OPT_PARM_lst['d']=1         OPT_VALUE_lst['d']=6

# We need OPT_OPT_lst to tell what the command option is, and OPT_PARM_lst to tell
# how many arguments this option required, though they are not used.
# shellcheck disable=SC2034
OPT_OPT_lst['F']='fmts'   OPT_DESC_lst['F']='Iterate all supported formats'
# shellcheck disable=SC2034
OPT_PARM_lst['F']=0         OPT_VALUE_lst['F']=0

func_opt_parse_option "$@"

duration=${OPT_VALUE_lst['d']}
loop_cnt=${OPT_VALUE_lst['l']}
tplg=${OPT_VALUE_lst['t']}

[[ ${OPT_VALUE_lst['s']} -eq 1 ]] && func_lib_start_log_collect

func_pipeline_export $tplg "codec_adapter:any"
func_lib_setup_kernel_last_line

[ "$PIPELINE_COUNT" == "1" ] || die "Detect $PIPELINE_COUNT pipeline(s) from topology, but one is needed"

pb_chan=$(func_pipeline_parse_value 0 ch_max)
pb_rate=$(func_pipeline_parse_value 0 rate)
pb_dev=$(func_pipeline_parse_value 0 dev)
pb_fmt=$(func_pipeline_parse_value 0 fmt)
pb_fmts=$(func_pipeline_parse_value 0 fmts)


fmts="$pb_fmt"
if [ ${OPT_VALUE_lst['F']} = '1' ]; then
    fmts="$pb_fmts"
fi

for i in $(seq 1 $loop_cnt)
do
    for fmt in $fmts
    do
        dlogi "Testing: iteration $i of $loop_cnt with $fmt format"
        # S16_LE and S24_LE format is not supported yet
        if [ "$fmt" != "S32_LE" ]; then
            continue
        fi
        # generate wave file
        tmp_dir="/tmp"
        file="$tmp_dir/codec_adap_${fmt%_*}.wav"
        recorded_file="$tmp_dir/codec_adap_recorded${fmt%_*}.wav"
        wavetool.py -gsine -A0.8 -B"${fmt%_*}" -o"$file"
        dlogc "aplay -D$pb_dev -r $pb_rate -c $pb_chan -f $fmt -d $duration -v -q $file &"
        aplay -D"$pb_dev" -r "$pb_rate" -c "$pb_chan" -f "$fmt" -d "$duration" -v -q "$file" &
        dlogc "arecord -D$pb_dev -r $pb_rate -c $pb_chan -f $fmt -d $duration -v -q $recorded_file"
        arecord -D"$pb_dev" -r "$pb_rate" -c "$pb_chan" -f "$fmt" -d "$duration" -v -q "$recorded_file"
        dlogi "Analyzing wave with wavetool.py"
        wavetool.py -a"thdn" -R"$recorded_file" || {
            # upload the failed wav file, and die
            find /tmp -maxdepth 1 -type f -name $(basename "$recorded_file") -size +0 -exec cp {} "$LOG_ROOT/" \;
            die "wavetool.py exit with failure"
        }
        sleep 2
    done
done

sof-kernel-log-check.sh "$KERNEL_LAST_LINE"
