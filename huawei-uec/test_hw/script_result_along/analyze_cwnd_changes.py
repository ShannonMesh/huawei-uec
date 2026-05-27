#!/usr/bin/env python3
import sys
import argparse
import re
import csv

def analyze_cwnd_changes(input_file, map_file, output_file):
    try:
        # Load flow mapping
        with open(map_file, 'r') as mapfile:
            reader = csv.DictReader(mapfile)
            flowid_to_uec = {}
            for row in reader:
                flowid_to_uec[row['flowid']] = row['flow_name']
        
        # Track cwnd state for each flow
        cwnd_state = {}
        events = []
        
        # First pass: collect all cwnd-related events
        with open(input_file, 'r') as infile:
            for line in infile:
                # Initialize event
                init_match = re.search(r'Initialize per-instance NSCC parameters: flowid (\d+) .*? _cwnd=(\d+)', line)
                if init_match:
                    flowid = init_match.group(1)
                    cwnd = int(init_match.group(2))
                    uec_name = flowid_to_uec.get(flowid, f"flowid_{flowid}")
                    events.append({
                        'type': 'Initialize',
                        'time': 0.0,
                        'flowid': flowid,
                        'flow_name': uec_name,
                        'cwnd': cwnd,
                        'reason': 'Initialize',
                        'change': cwnd,
                        'delay': '',
                        'skip': '',
                        'fair_inc': '',
                        'prop_inc': '',
                        'fast_inc': '',
                        'eta_inc': '',
                        'multi_dec': '',
                        'quick_dec': '',
                        'nack_dec': ''
                    })
                    cwnd_state[uec_name] = cwnd
                    continue
                
                # processAck event
                process_match = re.search(r'At ([\d.]+) (Uec_\d+_\d+) uecSrc \d+ processAck: \d+ flow (Uec_\d+_\d+) cwnd (\d+) flightsize \d+ delay ([\d.]+) newlyrecvd \d+ skip (\d+) raw rtt (\d+)', line)
                if process_match:
                    time = float(process_match.group(1))
                    flow_name = process_match.group(2)
                    cwnd = int(process_match.group(4))
                    delay = float(process_match.group(5))
                    skip = int(process_match.group(6))
                    raw_rtt = int(process_match.group(7))
                    
                    prev_cwnd = cwnd_state.get(flow_name, None)
                    change = cwnd - prev_cwnd if prev_cwnd is not None else 0
                    
                    # Determine reason based on delay and skip
                    if skip == 0 and delay < 1.0:
                        reason = 'Low delay + No ECN (proportional_increase + fast_increase)'
                    elif skip == 0 and delay < 10.0:
                        reason = 'Low delay + No ECN (proportional_increase)'
                    elif skip == 0 and delay >= 10.0:
                        reason = 'High delay + No ECN (fair_increase)'
                    elif skip == 1 and delay < 10.0:
                        reason = 'Low delay + ECN (NOOP)'
                    elif skip == 1 and delay >= 10.0:
                        reason = 'High delay + ECN (multiplicative_decrease)'
                    else:
                        reason = 'Unknown'
                    
                    events.append({
                        'type': 'processAck',
                        'time': time,
                        'flowid': '',
                        'flow_name': flow_name,
                        'cwnd': cwnd,
                        'reason': reason,
                        'change': change,
                        'delay': delay,
                        'skip': skip,
                        'fair_inc': '',
                        'prop_inc': '',
                        'fast_inc': '',
                        'eta_inc': '',
                        'multi_dec': '',
                        'quick_dec': '',
                        'nack_dec': ''
                    })
                    cwnd_state[flow_name] = cwnd
                    continue
                
                # proportional_increase event
                prop_match = re.search(r'([\d.]+) flowid (\d+) (Uec_\d+_\d+) proportional_increase _nscc_cwnd (\d+)', line)
                if prop_match:
                    time = float(prop_match.group(1))
                    flowid = prop_match.group(2)
                    flow_name = prop_match.group(3)
                    cwnd = int(prop_match.group(4))
                    
                    prev_cwnd = cwnd_state.get(flow_name, None)
                    change = cwnd - prev_cwnd if prev_cwnd is not None else 0
                    
                    events.append({
                        'type': 'proportional_increase',
                        'time': time,
                        'flowid': flowid,
                        'flow_name': flow_name,
                        'cwnd': cwnd,
                        'reason': 'Low delay + No ECN (proportional_increase)',
                        'change': change,
                        'delay': '',
                        'skip': '',
                        'fair_inc': '',
                        'prop_inc': '',
                        'fast_inc': '',
                        'eta_inc': '',
                        'multi_dec': '',
                        'quick_dec': '',
                        'nack_dec': ''
                    })
                    cwnd_state[flow_name] = cwnd
                    continue
                
                # fulfill_adjustmentx event
                fulfillx_match = re.search(r'([\d.]+) flowid (\d+) (Uec_\d+_\d+) fulfill_adjustmentx _nscc_cwnd (\d+) inc_bytes (-?\d+)', line)
                if fulfillx_match:
                    time = float(fulfillx_match.group(1))
                    flowid = fulfillx_match.group(2)
                    flow_name = fulfillx_match.group(3)
                    cwnd = int(fulfillx_match.group(4))
                    inc_bytes = int(fulfillx_match.group(5))
                    
                    prev_cwnd = cwnd_state.get(flow_name, None)
                    change = cwnd - prev_cwnd if prev_cwnd is not None else 0
                    
                    events.append({
                        'type': 'fulfill_adjustmentx',
                        'time': time,
                        'flowid': flowid,
                        'flow_name': flow_name,
                        'cwnd': cwnd,
                        'reason': 'Before fulfill_adjustment',
                        'change': change,
                        'delay': '',
                        'skip': '',
                        'fair_inc': '',
                        'prop_inc': '',
                        'fast_inc': '',
                        'eta_inc': '',
                        'multi_dec': '',
                        'quick_dec': '',
                        'nack_dec': ''
                    })
                    cwnd_state[flow_name] = cwnd
                    continue
                
                # Running fulfill adjustment event
                running_match = re.search(r'([\d.]+) flowid (\d+) Running fulfill adjustment cwnd (\d+) inc (-?\d+) fair_inc (-?\d+) prop_inc (-?\d+) fast_inc (-?\d+) eta_inc (-?\d+) multi_dec (-?\d+) quick_dec (-?\d+) nack_dec (-?\d+) avg-delay (\d+)', line)
                if running_match:
                    time = float(running_match.group(1))
                    flowid = running_match.group(2)
                    cwnd = int(running_match.group(3))
                    inc = int(running_match.group(4))
                    fair_inc = int(running_match.group(5))
                    prop_inc = int(running_match.group(6))
                    fast_inc = int(running_match.group(7))
                    eta_inc = int(running_match.group(8))
                    multi_dec = int(running_match.group(9))
                    quick_dec = int(running_match.group(10))
                    nack_dec = int(running_match.group(11))
                    avg_delay = int(running_match.group(12))
                    
                    # Determine the dominant reason
                    reasons = []
                    if fair_inc > 0:
                        reasons.append(f'fair_increase({fair_inc})')
                    if prop_inc > 0:
                        reasons.append(f'proportional_increase({prop_inc})')
                    if fast_inc > 0:
                        reasons.append(f'fast_increase({fast_inc})')
                    if eta_inc > 0:
                        reasons.append(f'eta_inc({eta_inc})')
                    if multi_dec < 0:
                        reasons.append(f'multiplicative_decrease({multi_dec})')
                    if quick_dec < 0:
                        reasons.append(f'quick_adapt({quick_dec})')
                    if nack_dec < 0:
                        reasons.append(f'nack_dec({nack_dec})')
                    
                    reason = ' + '.join(reasons) if reasons else 'No change'
                    
                    # Get flow name from flowid
                    flow_name = flowid_to_uec.get(flowid, '')
                    
                    prev_cwnd = cwnd_state.get(flow_name, None)
                    change = cwnd - prev_cwnd if prev_cwnd is not None else 0
                    
                    events.append({
                        'type': 'Running fulfill adjustment',
                        'time': time,
                        'flowid': flowid,
                        'flow_name': flow_name,
                        'cwnd': cwnd,
                        'reason': reason,
                        'change': change,
                        'delay': '',
                        'skip': '',
                        'fair_inc': fair_inc,
                        'prop_inc': prop_inc,
                        'fast_inc': fast_inc,
                        'eta_inc': eta_inc,
                        'multi_dec': multi_dec,
                        'quick_dec': quick_dec,
                        'nack_dec': nack_dec
                    })
                    cwnd_state[flow_name] = cwnd
                    continue
                
                # fulfill_adjustment event
                fulfill_match = re.search(r'([\d.]+) flowid (\d+) (Uec_\d+_\d+) fulfill_adjustment _nscc_cwnd (\d+)', line)
                if fulfill_match:
                    time = float(fulfill_match.group(1))
                    flowid = fulfill_match.group(2)
                    flow_name = fulfill_match.group(3)
                    cwnd = int(fulfill_match.group(4))
                    
                    prev_cwnd = cwnd_state.get(flow_name, None)
                    change = cwnd - prev_cwnd if prev_cwnd is not None else 0
                    
                    events.append({
                        'type': 'fulfill_adjustment',
                        'time': time,
                        'flowid': flowid,
                        'flow_name': flow_name,
                        'cwnd': cwnd,
                        'reason': 'After fulfill_adjustment',
                        'change': change,
                        'delay': '',
                        'skip': '',
                        'fair_inc': '',
                        'prop_inc': '',
                        'fast_inc': '',
                        'eta_inc': '',
                        'multi_dec': '',
                        'quick_dec': '',
                        'nack_dec': ''
                    })
                    cwnd_state[flow_name] = cwnd
                    continue
                
                # quick_adapt event
                quick_match = re.search(r'At ([\d.]+) (Uec_\d+_\d+) running quickadapt, CWND is (\d+) setting it to (\d+)', line)
                if quick_match:
                    time = float(quick_match.group(1))
                    flow_name = quick_match.group(2)
                    old_cwnd = int(quick_match.group(3))
                    new_cwnd = int(quick_match.group(4))
                    
                    events.append({
                        'type': 'quick_adapt',
                        'time': time,
                        'flowid': '',
                        'flow_name': flow_name,
                        'cwnd': new_cwnd,
                        'reason': f'quick_adapt: {old_cwnd} -> {new_cwnd}',
                        'change': new_cwnd - old_cwnd,
                        'delay': '',
                        'skip': '',
                        'fair_inc': '',
                        'prop_inc': '',
                        'fast_inc': '',
                        'eta_inc': '',
                        'multi_dec': '',
                        'quick_dec': '',
                        'nack_dec': ''
                    })
                    cwnd_state[flow_name] = new_cwnd
                    continue
        
        # Fill in missing flow names before sorting
        for event in events:
            flow_name = event.get('flow_name', '')
            if not flow_name:
                # Try to find flow name from flowid
                flowid = event.get('flowid', '')
                if flowid:
                    event['flow_name'] = flowid_to_uec.get(flowid, '')
        
        # Sort events by flow name and time (group by flow)
        events.sort(key=lambda x: (x['flow_name'], x['time']))
        
        # Write results
        with open(output_file, 'w') as outfile:
            header = "time,flow_name,cwnd,change,reason,delay,skip,fair_inc,prop_inc,fast_inc,eta_inc,multi_dec,quick_dec,nack_dec\n"
            outfile.write(header)
            for event in events:
                flow_name = event.get('flow_name', '')
                outfile.write(f"{event['time']},{flow_name},{event['cwnd']},{event['change']},{event['reason']},{event['delay']},{event['skip']},{event['fair_inc']},{event['prop_inc']},{event['fast_inc']},{event['eta_inc']},{event['multi_dec']},{event['quick_dec']},{event['nack_dec']}\n")
        
        print(f"Analyzed {len(events)} cwnd change events")
        print(f"Results saved to: {output_file}")
        
    except FileNotFoundError as e:
        print(f"Error: Input file '{e.filename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze cwnd changes with reasons')
    parser.add_argument('-i', '--input', required=True, help='Input file path')
    parser.add_argument('-m', '--map', required=True, help='Flow mapping CSV file path')
    parser.add_argument('-o', '--output', required=True, help='Output file path')
    
    args = parser.parse_args()
    
    analyze_cwnd_changes(args.input, args.map, args.output)
