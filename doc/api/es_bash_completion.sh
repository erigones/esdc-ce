#!/bin/sh
################################################################################
# bash completion for es - Erigones command-line tool
################################################################################
# Compatible with es >= 1.1
# Copyright (C) 2014 - 2016 Erigones, s. r. o.
#							info@erigones.com
################################################################################

__vm_hostname() {
	local resource=${COMP_WORDS[2]}
	local resource_array=(${resource//// })
	echo "${resource_array[1]}"
}

__vm_hostname_is_valid() {
	local hostname=$(__vm_hostname)
	case "${hostname}" in
		define|status|backup|snapshot)
			return 1
		;;
		*)
			return 0
		;;
	esac
}

_es() {
	local cur prev actions prefix action params
	local es_output="--json --csv --tabulate --tabulate-plain --tabulate-simple --tabulate-grid"
	local vm_define="-hostname -alias -template -ostype -vcpus -owner -node -tags -monitored -installed -snapshot_limit_manual -zpool -cpu_shares -zfs_io_priority -mdata -full -routes"
	local vm_snapshot="-disk_id -note -force"
	local vm_backup="-disk_id -note"

    COMPREPLY=()
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	prefix=""
	actions="set get create logout login options delete"

    if [ ${COMP_CWORD} -eq 1 ]; then
		COMPREPLY=( $( compgen -W "${actions}" -- "${cur}" ) )
		COMPREPLY=( "${COMPREPLY[@]/%/ }" )
	else
		case "${COMP_WORDS[1]}" in
			"logout")
				return 0
			;;

			"login")
				if [[ "${cur}" == -* ]]; then
					COMPREPLY=( $( compgen -W "-username -password" -- "${cur}" ) )
					COMPREPLY=( "${COMPREPLY[@]/%/ }" )
				fi
				return 0
			;;

			"get"|"create"|"set"|"delete"|"options")
				if [ ${COMP_CWORD} -lt 3 ]; then
					COMPREPLY=( $( compgen -W "/vm/define /vm/define/snapshot /vm/define/backup /vm/status /vm/ /vm/(hostname) /mon/ /mon/vm/ /mon/node/ /node/ /node/(hostname) /dc/ /dc/(dc) /network/ /network/ip/ /network/(name) /image/ /image/(name) /imagestore/ /imagestore/(name) /template/ /template/(name) /iso/ /iso/(name) /dns/domain/ /dns/domain/(name) /task/log /task/ /task/(task_id) /system/ /accounts/login /accounts/logout /accounts/user /accounts/permission /accounts/group" -- "${cur}" ) )
				fi
			;;
			*)
				return 0
			;;
		esac
	fi

	action=${COMP_WORDS[1]}
	params=""

	case "${COMP_WORDS[2]}" in
		/accounts/login|/accounts/login/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-username -password"
		;;

		/accounts/logout|/accounts/logout/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
		;;

		/accounts/user/profile|/accounts/user/profile/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}") )
			fi
			[[ "${action}" == "get" ]] && params="-order_by"
		;;

		/accounts/user/*/profile|/accounts/user/*/profile/)
			[[ "${action}" == "set" ]] && params="-tos_acceptation -email_verified -email2 -email2_verified -phone -phone_verified -phone2 -phone2_verified -newsletter_tech -newsletter_buss -usertype -language -timezone -currency -title -middle_name -website -jabber -street_1 -street2_1 -city -postcode -state -country -different_billing -street_2 -street2_2 -city2 -postcode2 -state2 -country2 -company -companyid -taxid -vatid -bankid"	
		;;

		/accounts/user/*/sshkey/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(title)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] && params="-key"
		;;

		/accounts/user/*/sshkey|/accounts/user/*/sshkey/)
			[[ "${action}" == "get" ]] && params="-full"
		;;

		/accounts/user/*/apikeys|/accounts/user/*/apikeys/)
			[[ "${action}" == "set" ]] && params="-api_key -callback_key"
		;;

		/accounts/user|/accounts/user/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(username)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "get" ]] && params="-full -extended -is_active -order_by"
		;;

		/accounts/user/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/profile /sshkey" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] && params="-first_name -last_name -api_access -api_key -callback_key -is_active -is_super_admin -email -groups -dc_bound -password"
			[[ "${action}" == "set" ]] && params="-username -first_name -last_name -api_access -api_key -callback_key -is_active -is_super_admin -email -groups -dc_bound -password"
		;;

		/accounts/permission|/accounts/permission/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(name)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "get" ]] && params="-full"
		;;

		/accounts/group|/accounts/group/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(name)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/accounts/group/*)
			[[ "${action}" == "get" ]] && params="-extended"
			[[ "${action}" == "create" ]] && params="-alias -users -permissions -dc -dc_bound -dcs"
			[[ "${action}" == "set" ]] && params="-name -alias -users -permissions -dc_bound -dcs"
		;;

		/task/log|/task/log/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-page -status -object_type -object_name -show_running -hide_auto -date_from -date_to"
		;;

		/task/*/*/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
		;;

		/task/*/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /done /status /cancel" -- "/${cur##*/}" ) )
				COMPREPLY=( "${COMPREPLY[@]/%/ }" )
			fi
		;;

		/system/node/version|/system/node/version/)
			params=""
		;;

		/system/node/*/version|/system/node/*/version/)
			params=""
		;;

		/system/node/*/service/status|/system/node/*/service/status/)
			params=""
		;;

		/system/node/*/logs|/system/node/*/logs/)
			[[ "${action}" == "get" ]] && params="-logname"
		;;

		/system/node/*/update|/system/node/*/update/)
			[[ "${action}" == "set" ]] && params="-version -key -cert"
		;;

		/system/node/*/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/version /service/status /update /logs" -- "/${cur##*/}" ) )
				COMPREPLY=( "${COMPREPLY[@]/%/ }" )
			fi
		;;

		/system/node/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/version /(hostname) /(hostname)/version /(hostname)/service/status /(hostname)/logs /(hostname)/update" -- "/${cur##*/}" ) )
				COMPREPLY=( "${COMPREPLY[@]/%/ }" )
			fi
		;;

		/system/service/status|/system/service/status/)
			params=""
		;;

		/system/version)
			params=""
		;;

		/system/update)
			[[ "${action}" == "set" ]] && params="-version -key -cert"
		;;

		/system/settings/ssl-certificate)
			[[ "${action}" == "set" ]] && params="-cert"
		;;

		/system/logs|/system/logs/)
			[[ "${action}" == "get" ]] && params="-logname"
		;;

		/system/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/version /service/status /update /node/version /node/(hostname)/version /node/(hostname)/service/status /node/(hostname)/update /node/(hostname)/logs /logs /settings/ssl-certificate" -- "/${cur##*/}" ) )
				COMPREPLY=( "${COMPREPLY[@]/%/ }" )
			fi
		;;

		/vm/define|/vm/define/)
			[[ "${action}" == "get" ]] && params="-full -active"
		;;

		/vm/define/snapshot|/vm/define/snapshot/|/vm/define/backup|/vm/define/backup/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/vm/status|/vm/status/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
		;;

		/vm/*/status/start|/vm/*/status/start/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-cdimage -update -cb_url -cb_method"
		;;

		/vm/*/status/stop|/vm/*/status/stop/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-force -freeze -unfreeze -cb_url -cb_method"
		;;

		/vm/*/status/reboot|/vm/*/status/reboot/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-force -cb_url -cb_method"
		;;

		/vm/*/status|/vm/*/status/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /start /stop /reboot" -- "/${cur##*/}" ) )
				COMPREPLY=( "${COMPREPLY[@]/%/ }" )
			fi
		;;

		/vm/*/define/disk/*)
			params="-size -image -model -block_size -compression -zpool -boot -refreservation"
			[[ "${action}" == "get" ]] && params="-active"
		;;

		/vm/*/define/nic/*)
			params="-net -ip -model -monitoring -dns -use_net_dns -mac -allow_dhcp_spoofing -allow_ip_spoofing -allow_mac_spoofing -allow_restricted_traffic -allow_unfiltered_promisc -allowed_ips -set_gateway"
			[[ "${action}" == "get" ]] && params="-active"
		;;

		/vm/*/define/snapshot/*)
			params="-disk_id -desc -schedule -retention -active"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/vm/*/define/backup/*)
			params="-disk_id -desc -schedule -retention -active -node -zpool -rate_limit"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;


		/vm/*/define/nic/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(nic_id)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "get" ]] && params="-active"
		;;

		/vm/*/define/disk/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(disk_id)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "get" ]] && params="-active"
		;;

		/vm/*/define/snapshot/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(snapdef)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/vm/*/define/backup/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(bkpdef)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/vm/*/define/snapshot|/vm/*/define/backup)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/vm/*/define/disk|/vm/*/define/nic)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-active"
		;;

		/vm/*/define)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			if [[ "${action}" == "get" ]]; then
				params="-full -active"
			else
				params=${vm_define}
			fi
		;;

		/vm/*/define/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /nic /nic/(nic_id) /disk /disk/(disk_id) /snapshot /snapshot/(snapdef) /backup /backup/(bkpdef) /revert" -- "/${cur##*/}" ) )
			fi
			if [[ "${action}" == "get" ]]; then
				params="-full -active"
			else
				params=${vm_define}
			fi
		;;

		/vm/*/snapshot/*/)
			params="${vm_snapshot} -cb_url -cb_method"
		;;

		/vm/*/snapshot)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			params="-full -disk_id -type -define"
		;;

		/vm/*/snapshot/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(snapname)" -- "/${cur##*/}" ) )
			fi
			params="${vm_snapshot} -type -define -cb_url -cb_method"
		;;

		/vm/*/backup/*/)
			params=${vm_backup}
		;;

		/vm/*/backup)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			params="-full -disk_id -define"
		;;

		/vm/*/backup/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				if [[ "${action}" == "create" ]]; then
					COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(bkpdef)" -- "/${cur##*/}" ) )
				else
					COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(bkpname)" -- "/${cur##*/}" ) )
				fi
			fi
			params="${vm_backup} -define -cb_method -cb_url"
		;;

		/vm/*/replica)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			params="-full"
		;;

		/vm/*/replica/*/failover|/vm/*/replica/*/failover/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-force -cb_method -cb_url"
		;;

		/vm/*/replica/*/reinit|/vm/*/replica/*/reinit/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-cb_method -cb_url"
		;;

		/vm/*/replica/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(repname)" -- "/${cur##*/}" ) )
			fi
			if [[ "${action}" == "create" ]]; then
				params="-node -root_zpool -disk_zpools -sleep_time -enabled -bwlimit -cb_url -cb_method"
			elif [[ "${action}" == "set" ]]; then
				params="-sleep_time -enabled -bwlimit -cb_url -cb_method"
			elif [[ "${action}" == "delete" ]]; then
				params="-cb_url -cb_method"
			else
				params=""
			fi
		;;

		/vm/*/migrate|/vm/*/migrate/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-node -root_zpool -disk_zpools -cb_method -cb_url"
		;;

		/vm/*/monitoring|/vm/*/monitoring/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			if [[ "${action}" == "set" ]]; then
				params="-ip -port -dns -useip -proxy -hostgroups -templates"
			else
				params=""
			fi
		;;

		/vm/*/screenshot|/vm/*/screenshot/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			params="-cb_url -cb_method"
		;;

		/vm/*/qga)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
		;;

		/vm/*/qga/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/info /sync /ping /fsfreeze /reboot /poweroff /get-time /set-time" -- "/${cur##*/}" ) )
			fi
			if [[ "${action}" == "set" ]]; then
				params="-params -cb_url -cb_method"
			else
				params=""
			fi
		;;

		/vm/*/*)
			if __vm_hostname_is_valid; then
				if [ ${COMP_CWORD} -eq 2 ]; then
					COMPREPLY=( $(compgen -P "${cur%/*}" -W "/status/ /define/ /snapshot/ /backup/ /screenshot /migrate/dc /migrate /replica /monitoring /qga" -- "/${cur##*/}" ) )
				fi
				[[ "${action}" == "create" ]] && params="-recreate -force"
			fi
		;;

		/vm/*)
			[[ "${action}" == "create" ]] && params="-recreate -force"
			[[ "${action}" == "get" ]] && params="-active -extended"
		;;

		/vm)
			[[ "${action}" == "get" ]] && params="-full -active -extended"
		;;

		/dc/*/node)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/dc/*/node/*)

			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(hostname)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-strategy -cpu -ram -disk -priority"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/dc/*/storage)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/dc/*/storage/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(zpool@node)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params=""
		;;

		/dc/*/network|/dc/*/image|/dc/*/template|/dc/*/iso|/dc/*/domain)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-full"
		;;

		/dc/*/network/*|/dc/*/image/*|/dc/*/template/*|/dc/*/iso/*|/dc/*/domain/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(name)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] || [[ "${action}" == "delete" ]] && params=""
		;;

		/dc/*/user)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-full -active"
		;;

		/dc/*/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/node/ /storage/ /network/ /image/ /template/ /iso/ /domain/ /user/ /group/ /settings" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-alias -access -owner -desc -site -groups"
		;;

		/dc|/dc/*)
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-alias -access -owner -desc -site -groups"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/mon/vm/*/sla/|/mon/node/*/sla/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(yyyymm)" -- "/${cur##*/}" ) )
			fi
		;;

		/mon/vm/*/history/|/mon/node/*/history/)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(graph)" -- "/${cur##*/}" ) )
			fi
		;;

		/mon/vm/*/*|/mon/node/*/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /monitoring /sla/ /history/" -- "/${cur##*/}" ) )
			fi
		;;

		/mon/vm/*|/mon/node/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(hostname)/" -- "/${cur##*/}" ) )
			fi
		;;

		/node/*/storage)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/node/*/storage/*/image)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-full"
		;;

		/node/*/storage/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(zpool) /(zpool)/image" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-alias -access -owner -type -size_coef -desc"
			[[ "${action}" == "get" ]] && params="-extended"
		;;

		/node/*/define|/node/*/define/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			[[ "${action}" == "get" ]] && params="-full"
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-status -is_compute -is_backup -owner -cpu_coef -ram_coef"
		;;

		/node/*/license|/node/*/license/)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			[[ "${action}" == "set" ]] && params="-license"
		;;

		/node/*/sysinfo)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur} " )
			[[ "${action}" == "set" ]]
		;;

		/node/*/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/define/ /storage/ /license /sysinfo" -- "/${cur##*/}" ) )
			fi
		;;

		/node/*)
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/node)
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/network/ip)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			params="-full"
		;;

		/network/ip/*)
			params="-full"
		;;

		/network/*/ip)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			params="-full"
		;;

		/network/*/ip/*)

			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(ip)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" != "get" ]] && params=""
		;;

		/network/*/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ip/" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-alias -access -owner -desc -network -netmask -gateway -nic_tag -vlan_id -resolvers"
		;;

		/network/*)
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-alias -access -owner -desc -network -netmask -gateway -nic_tag -vlan_id -resolvers -dc_bound"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/image/*)
			[[ "${action}" == "create" ]] && params="-manifest_url -file_url -alias -version -access -owner -desc -ostype -deploy -resize -dc -dc_bound -cb_method -cb_url"
			[[ "${action}" == "set" ]] && params="-alias -version -access -owner -desc -ostype -deploy -resize -dc_bound -cb_method -cb_url"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/imagestore/*/image)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			[[ "${action}" == "get" ]] && params="-full"
		;;

		/imagestore/*/image/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(uuid)" -- "/${cur##*/}" ) )
			fi
			if [[ "${action}" == "get" ]]; then
				params="-full"
			elif [[ "${action}" == "create" ]]; then
				params="-name -alias -version -access -owner -desc -ostype -deploy -resize -dc -dc_bound -cb_method -cb_url"
			else
				params=""
			fi
		;;

		/imagestore/*/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/image/" -- "/${cur##*/}" ) )
			fi
			if [[ "${action}" == "get" ]]; then
				params="-full"
			else
				params=""
			fi
		;;

		/imagestore/*|/imagestore)
			if [[ "${action}" == "get" ]]; then
				params="-full"
			else
				params=""
			fi
		;;

		/template/*)
			[[ "${action}" == "create" ]] && params="-alias -access -owner -desc -ostype -dc"
			[[ "${action}" == "set" ]] && params="-alias -access -owner -desc -ostype -dc_bound"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/iso/*)
			[[ "${action}" == "create" ]] && params="-alias -access -owner -desc -ostype -dc"
			[[ "${action}" == "set" ]] && params="-alias -access -owner -desc -ostype -dc_bound"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;

		/dns/domain/*/record)
			[ ${COMP_CWORD} -eq 2 ] && COMPREPLY=( "${cur}/" )
			params="-full"
		;;

		/dns/domain/*/record/*)

			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/ /(record_id)" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" != "get" ]] && params=""
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-name -type -content -ttl -prio -disabled"
		;;

		/dns/domain/*/*)
			if [ ${COMP_CWORD} -eq 2 ]; then
				COMPREPLY=( $(compgen -P "${cur%/*}" -W "/record/" -- "/${cur##*/}" ) )
			fi
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-name -owner -type -master -access -desc"
		;;

		/dns/domain/*)
			[[ "${action}" == "create" ]] || [[ "${action}" == "set" ]] && params="-name -owner -type -master -access -desc"
			[[ "${action}" == "get" ]] && params="-full -extended"
		;;


		*)
			if [[ "${action}" == "get" ]] && [[ "${cur}" == --* ]]; then
				COMPREPLY=( $( compgen -W "${es_output}" -- "${cur}" ) )
				COMPREPLY=( "${COMPREPLY[@]/%/ }" )
			fi

			return 0
		;;
	esac

	if [ -n "${params}" ] && [[ "${cur}" == -* ]]; then
		COMPREPLY=( $( compgen -W "${params}" -- "${cur}" ) )
		COMPREPLY=( "${COMPREPLY[@]/%/ }" )
	fi

	if [[ "${action}" == "get" ]] && [[ "${cur}" == --* ]]; then
		COMPREPLY=( $( compgen -W "${es_output}" -- "${cur}" ) )
		COMPREPLY=( "${COMPREPLY[@]/%/ }" )
	fi

	return 0
}

complete -F _es -o nospace es
