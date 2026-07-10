#!/data/data/com.termux/files/usr/bin/bash
set -e
pkg update
pkg install -y python python-numpy git tmux curl
python -m pip install -r requirements-termux.txt
cp -n .env.example .env || true
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/market-bot.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$(pwd)"
./termux_run.sh
EOF
chmod +x "$HOME/.termux/boot/market-bot.sh" termux_run.sh
printf '\n✅ تم الإعداد. نفّذ: ./termux_run.sh\n'
printf 'للتشغيل بعد إعادة الهاتف ثبّت Termux:Boot من F-Droid وافتحه مرة واحدة.\n'
