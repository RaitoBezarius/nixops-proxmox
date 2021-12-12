#!/usr/bin/env nix-shell
#! nix-shell -i bash -p dasel
# TODO: finish me.
CONFIGURATION_FILE=${PROXMOX_CREDENTIALS_FILE:-$XDG_CONFIG_HOME/proxmox/credentials}
function put_string() {
	dasel put string -p toml -f "${CONFIGURATION_FILE}" "$@"
}

function configure_username_and_password() {
	local profile_name="$1"
	read -p "Enter the username: " username
	put_string ".${profile_name}.username" $username
	read -p "Enter the password: " -s password
	put_string ".${profile_name}.password" $password
}

function configure_node() {
	echo "TODO"
}

function configure_pool() {
	echo "TODO"
}

function configure_token() {
	echo "test"
}

function configure_server_url() {
	local profile_name="$1"
	echo -ne "Enter the server URL in the format: protocol://url:port\n"
	read server_url
	put_string ".${profile_name}.server_url" $server_url
}

function ensure_credentials_file_exists() {
	local config_dir=$(dirname "${CONFIGURATION_FILE}")
	if [ ! -d $config_dir ] ;
	then
		echo "Credentials directory did not exist, creating the directories..."
		mkdir -p $config_dir
		chmod -R 700 $config_dir
	fi

	if [ ! -f $CONFIGURATION_FILE ] ;
	then
		echo "Credentials file do not exist, creating the file..."
		touch $CONFIGURATION_FILE
		chmod 600 $CONFIGURATION_FILE
	fi
}

function ensure_right_permissions_for_credentials() {
	# test if credentials file is rw for user only.
	echo "TODO: verify permissions"
}

function profile_exists() {
	echo "TODO: check if profile exists"
	false
}

function configure_profile() {
	ensure_credentials_file_exists
	ensure_right_permissions_for_credentials
	read -p "Enter the profile name: " profile_name
	if profile_exists $profile_name ;
	then
		echo "This profile already exists! Please delete it."
		exit 1
	fi
	configure_server_url $profile_name
	echo -n "
	Which authentication method do you want to use?
	1) Username and password
	2) Token
	3) SSH
	Choose an option: "
	read choice
	case $choice in
		1) configure_username_and_password $profile_name ;;
		2) configure_token $profile_name ;;
		3) configure_ssh $profile_name ;;
		*) echo -e "Wrong option." ;;
	esac
	echo "Profile configured in ${CONFIGURATION_FILE}!"
}

configure_profile
