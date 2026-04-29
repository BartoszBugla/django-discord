from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q

from .models import Profile, Channel, ChannelMember, Message, BlockedUser, Reaction
from .forms import RegisterForm, ProfileForm, ChannelForm, MessageForm


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.is_online = True
            profile.save()
            login(request, user)
            return redirect('chat:home')
    else:
        form = RegisterForm()
    return render(request, 'chat/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.is_online = True
            profile.save()
            next_url = request.POST.get('next', request.GET.get('next', '/'))
            return redirect(next_url)
        else:
            messages.error(request, 'Nieprawidlowy login lub haslo.')
    return render(request, 'chat/login.html')


@login_required
def logout_view(request):
    profile = getattr(request.user, 'profile', None)
    if profile:
        profile.is_online = False
        profile.save()
    logout(request)
    return redirect('chat:login')


@login_required
def home(request):
    channels = Channel.objects.all()
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/home.html', {
        'channels': channels,
        'all_channels': all_channels,
    })


@login_required
def profile_view(request, user_id):
    viewed_user = get_object_or_404(User, pk=user_id)
    profile, _ = Profile.objects.get_or_create(user=viewed_user)
    is_blocked = BlockedUser.objects.filter(
        blokujacy=request.user, zablokowany=viewed_user
    ).exists()
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/profile.html', {
        'viewed_user': viewed_user,
        'profile': profile,
        'is_blocked': is_blocked,
        'all_channels': all_channels,
    })


@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil zaktualizowany!')
            return redirect('chat:profile', user_id=request.user.id)
    else:
        form = ProfileForm(instance=profile)
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/edit_profile.html', {
        'form': form,
        'all_channels': all_channels,
    })


@login_required
def create_channel(request):
    if request.method == 'POST':
        form = ChannelForm(request.POST)
        if form.is_valid():
            channel = form.save(commit=False)
            channel.tworca = request.user
            channel.save()
            ChannelMember.objects.create(user=request.user, channel=channel)
            return redirect('chat:channel', channel_id=channel.id)
    else:
        form = ChannelForm()
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/create_channel.html', {
        'form': form,
        'all_channels': all_channels,
    })


@login_required
def channel_view(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    is_member = ChannelMember.objects.filter(user=request.user, channel=channel).exists()

    if not is_member:
        return redirect('chat:join_channel', channel_id=channel.id)

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.autor = request.user
            msg.channel = channel
            msg.save()
            return redirect('chat:channel', channel_id=channel.id)

    wiadomosci = Message.objects.filter(channel=channel).select_related('autor', 'autor__profile')
    members = ChannelMember.objects.filter(channel=channel).select_related('user', 'user__profile')
    all_channels = Channel.objects.filter(members__user=request.user)
    emojis = ['👍', '👎', '❤️', '😂', '😮', '😢', '🔥', '🎉']

    all_reactions = Reaction.objects.filter(message__channel=channel)
    grouped = {}
    for r in all_reactions:
        key = (r.message_id, r.emoji)
        if key not in grouped:
            grouped[key] = {'emoji': r.emoji, 'count': 0, 'mine': False}
        grouped[key]['count'] += 1
        if r.user_id == request.user.id:
            grouped[key]['mine'] = True

    reactions_map = {}
    for (msg_id, emoji), data in grouped.items():
        reactions_map.setdefault(msg_id, []).append(data)

    return render(request, 'chat/channel.html', {
        'channel': channel,
        'wiadomosci': wiadomosci,
        'members': members,
        'all_channels': all_channels,
        'emojis': emojis,
        'reactions_map': reactions_map,
    })


@login_required
def join_channel(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    ChannelMember.objects.get_or_create(user=request.user, channel=channel)
    return redirect('chat:channel', channel_id=channel.id)


@login_required
def delete_channel(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    if request.user == channel.tworca or _is_admin(request.user):
        channel.delete()
        messages.success(request, 'Kanal usuniety.')
    else:
        messages.error(request, 'Brak uprawnien do usuniecia kanalu.')
    return redirect('chat:home')


@login_required
def dm_list(request):
    sent = Message.objects.filter(autor=request.user, channel__isnull=True).values_list('odbiorca', flat=True)
    received = Message.objects.filter(odbiorca=request.user, channel__isnull=True).values_list('autor', flat=True)
    user_ids = set(list(sent) + list(received))
    users = User.objects.filter(id__in=user_ids)
    all_users = User.objects.exclude(id=request.user.id)
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/dm_list.html', {
        'users': users,
        'all_users': all_users,
        'all_channels': all_channels,
    })


@login_required
def dm_view(request, user_id):
    other_user = get_object_or_404(User, pk=user_id)

    is_blocked = BlockedUser.objects.filter(
        blokujacy=other_user, zablokowany=request.user
    ).exists()

    if request.method == 'POST' and not is_blocked:
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.autor = request.user
            msg.odbiorca = other_user
            msg.save()
            return redirect('chat:dm', user_id=other_user.id)

    wiadomosci = Message.objects.filter(
        Q(autor=request.user, odbiorca=other_user) |
        Q(autor=other_user, odbiorca=request.user),
        channel__isnull=True
    ).select_related('autor', 'autor__profile')
    all_channels = Channel.objects.filter(members__user=request.user)

    return render(request, 'chat/dm.html', {
        'other_user': other_user,
        'wiadomosci': wiadomosci,
        'all_channels': all_channels,
        'is_blocked': is_blocked,
    })


def _is_moderator_or_admin(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile.role in ('admin', 'moderator') or user.is_superuser


@login_required
def delete_message(request, message_id):
    msg = get_object_or_404(Message, pk=message_id)

    if request.user == msg.autor or _is_moderator_or_admin(request.user):
        redirect_url = request.POST.get('next', '/')
        msg.delete()
        messages.success(request, 'Wiadomosc usunieta.')
        return redirect(redirect_url)
    return redirect('chat:home')


@login_required
def add_reaction(request, message_id):
    msg = get_object_or_404(Message, pk=message_id)
    emoji = request.POST.get('emoji', '')
    if emoji:
        reaction, created = Reaction.objects.get_or_create(
            user=request.user, message=msg, emoji=emoji
        )
        if not created:
            reaction.delete()
    next_url = request.POST.get('next', '/')
    return redirect(next_url)


@login_required
def block_user(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if request.user != target:
        BlockedUser.objects.get_or_create(blokujacy=request.user, zablokowany=target)
        messages.success(request, f'Uzytkownik {target.username} zablokowany.')
    return redirect('chat:profile', user_id=user_id)


@login_required
def unblock_user(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    BlockedUser.objects.filter(blokujacy=request.user, zablokowany=target).delete()
    messages.success(request, f'Uzytkownik {target.username} odblokowany.')
    return redirect('chat:profile', user_id=user_id)


def _is_admin(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile.role == 'admin' or user.is_superuser


@login_required
def change_role(request, user_id):
    if not _is_admin(request.user):
        messages.error(request, 'Brak uprawnien.')
        return redirect('chat:home')

    target = get_object_or_404(User, pk=user_id)
    target_profile, _ = Profile.objects.get_or_create(user=target)
    new_role = request.POST.get('role', 'user')
    if new_role in ('admin', 'moderator', 'user'):
        target_profile.role = new_role
        target_profile.save()
        messages.success(request, f'Rola zmieniona na {new_role}.')
    return redirect('chat:profile', user_id=user_id)


@login_required
def search_view(request):
    query = request.GET.get('q', '')
    users = User.objects.none()
    channels = Channel.objects.none()
    if query:
        users = User.objects.filter(username__icontains=query)
        channels = Channel.objects.filter(nazwa__icontains=query)
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/search.html', {
        'query': query,
        'users': users,
        'channels': channels,
        'all_channels': all_channels,
    })


@login_required
def leave_channel(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    ChannelMember.objects.filter(user=request.user, channel=channel).delete()
    messages.success(request, f'Opuszczono kanal {channel.nazwa}.')
    return redirect('chat:home')


@login_required
def admin_users(request):
    if not _is_admin(request.user):
        messages.error(request, 'Brak uprawnien.')
        return redirect('chat:home')

    users = User.objects.select_related('profile').all()
    channels = Channel.objects.all()
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/admin_users.html', {
        'users': users,
        'channels': channels,
        'all_channels': all_channels,
    })


def custom_404(request, exception):
    return render(request, 'chat/404.html', status=404)
