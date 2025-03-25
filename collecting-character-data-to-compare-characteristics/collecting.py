import time
import json
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup

# Основной URL для сбора данных
base_url = "https://eldenring.fandom.com/wiki/Category:Characters"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Получаем HTML страницы со списком персонажей
response = requests.get(base_url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

# Найти все ссылки на персонажей
character_links = []
character_containers = soup.find_all('a', class_='category-page__member-link')

for char in character_containers:
    character_links.append({
        'name': char.text.strip(),
        'url': 'https://eldenring.fandom.com' + char['href']
    })

print(f"Найдено {len(character_links)} персонажей")

# Пропускаем первые 13 записей, так как они не персонажи
character_links = character_links[13:]
print(f"После фильтрации осталось {len(character_links)} персонажей")

# Сбор данных о каждом персонаже
characters_data = []

for idx, char in enumerate(character_links[:50]):  # Ограничимся первыми 50 персонажами
    print(f"Обрабатываю {idx+1}/{len(character_links[:50])}: {char['name']}")
    
    # Делаем паузу между запросами, чтобы не перегружать сервер
    time.sleep(1)
    
    # Получаем HTML страницы персонажа
    char_response = requests.get(char['url'], headers=headers)
    char_soup = BeautifulSoup(char_response.content, 'html.parser')
    
    # Базовая информация
    character_info = {
        'name': char['name'],
        'url': char['url'],
        'faction': 'Unknown',
        'location': 'Unknown',
        'role': 'Unknown',
        'health': 0,
        'has_quest': False,
        'is_boss': False,
        'is_miniboss': False,
        'is_npc': False,
        'is_hostile': False,
        'is_friendly': False,
        'character_type': 'Unknown'  # Новое поле для типа персонажа
    }
    
    # Извлечение информации из infobox
    infobox = char_soup.find('aside', class_='portable-infobox')
    
    # Получаем полный текст страницы для анализа
    page_text = char_soup.get_text().lower()
    
    # Извлечение ключевой информации из infobox
    if infobox:
        # Фракция
        faction_tag = infobox.find('div', {'data-source': 'faction'})
        if faction_tag:
            faction_value = faction_tag.find('div', class_='pi-data-value')
            if faction_value:
                faction_links = faction_value.find_all('a')
                if faction_links and len(faction_links) > 1:
                    factions = [link.text.strip() for link in faction_links]
                    character_info['faction'] = ', '.join(factions)
                else:
                    character_info['faction'] = faction_value.text.strip()
        
        # Локация
        location_tag = infobox.find('div', {'data-source': 'location'})
        if location_tag:
            location_value = location_tag.find('div', class_='pi-data-value')
            if location_value:
                location_links = location_value.find_all('a')
                if location_links and len(location_links) > 1:
                    locations = [link.text.strip() for link in location_links]
                    character_info['location'] = ', '.join(locations)
                else:
                    location_text = location_value.text.strip()
                    if ',' in location_text or '\n' in location_text:
                        locations = [loc.strip() for loc in re.split(r'[,\n]', location_text) if loc.strip()]
                        character_info['location'] = ', '.join(locations)
                    else:
                        character_info['location'] = location_text
        
        # Роль - ключевой фактор для определения типа персонажа
        role_tag = infobox.find('div', {'data-source': 'role'})
        if role_tag:
            role_value = role_tag.find('div', class_='pi-data-value')
            if role_value:
                role_links = role_value.find_all('a')
                if role_links and len(role_links) > 1:
                    roles = [link.text.strip() for link in role_links]
                    character_info['role'] = ', '.join(roles)
                else:
                    role_text = role_value.text.strip()
                    if ',' in role_text or '\n' in role_text:
                        roles = [role.strip() for role in re.split(r'[,\n]', role_text) if role.strip()]
                        character_info['role'] = ', '.join(roles)
                    else:
                        character_info['role'] = role_text
    
    # Извлечение значения здоровья (для информации, но не для определения типа персонажа)
    if infobox:
        health_tag = infobox.find('div', {'data-source': 'health'})
        if health_tag:
            health_value_div = health_tag.find('div', class_='pi-data-value')
            if health_value_div:
                health_value = health_value_div.find(class_='pi-font')
                if not health_value:
                    health_value = health_value_div
                
                if health_value:
                    health_text = health_value.text.strip()
                    health_match = re.search(r'(\d[\d,]+)', health_text)
                    if health_match:
                        try:
                            character_info['health'] = int(health_match.group(1).replace(',', ''))
                        except:
                            pass
    
    # ОПРЕДЕЛЕНИЕ ТИПА ПЕРСОНАЖА НА ОСНОВЕ РОЛИ И КОНТЕКСТА
    
    # 1. Определение босса
    boss_score = 0
    
    # Ключевые слова боссов
    boss_keywords = ['boss', 'demigod', 'shardbearer', 'remembrance', 'great enemy', 'legend']
    for keyword in boss_keywords:
        if keyword in page_text:
            boss_score += 1
    
    # Признаки босса в роли
    if character_info['role'] and any(term in character_info['role'].lower() for term in boss_keywords):
        boss_score += 3
    
    # Наличие разделов, типичных для боссов
    boss_sections = ['moveset', 'strategy', 'strategies', 'phases', 'attacks']
    page_headers = char_soup.find_all(['h2', 'h3'])
    for header in page_headers:
        header_text = header.text.lower()
        for section in boss_sections:
            if section in header_text:
                boss_score += 1
                break
    
    # Упоминание фаз боя
    if char_soup.find(text=re.compile(r'phase\s+\d', re.IGNORECASE)):
        boss_score += 2
    
    # Очевидные указания на босса в тексте
    if "this boss" in page_text or "defeat the boss" in page_text:
        boss_score += 2
    
    character_info['is_boss'] = boss_score >= 4
    
    # 2. Определение мини-босса
    miniboss_score = 0
    
    # Ключевые слова мини-боссов
    miniboss_keywords = ['mini-boss', 'miniboss', 'field boss', 'dungeon boss', 'evergaol', 'enemy boss']
    for keyword in miniboss_keywords:
        if keyword in page_text:
            miniboss_score += 2
    
    # Признаки мини-босса в роли
    if character_info['role'] and any(term in character_info['role'].lower() for term in miniboss_keywords):
        miniboss_score += 3
    
    # Если персонаж похож на босса, но не дотягивает
    if 2 <= boss_score < 4:
        miniboss_score += 1
    
    character_info['is_miniboss'] = not character_info['is_boss'] and miniboss_score >= 2
    
    # 3. Определение NPC
    npc_score = 0
    
    # Прямое указание на NPC в инфобоксе
    if infobox and (infobox.find(text=re.compile(r'\bNPC\b', re.IGNORECASE)) or 
                    (character_info['role'] and 'npc' in character_info['role'].lower())):
        npc_score += 3
    
    # Ключевые слова, указывающие на NPC
    npc_keywords = ['merchant', 'vendor', 'shopkeeper', 'questgiver', 'blacksmith', 'resident', 'ally']
    for keyword in npc_keywords:
        if keyword in page_text:
            npc_score += 1
            if keyword in character_info['role'].lower() if character_info['role'] else False:
                npc_score += 1  # Дополнительные очки, если это указано в роли
    
    # Наличие диалогов
    if 'dialogue' in page_text or 'dialog' in page_text:
        npc_score += 1
        # Проверим, есть ли целые разделы с диалогами
        if char_soup.find(['h2', 'h3'], string=re.compile(r'dialog|dialogue', re.IGNORECASE)):
            npc_score += 2
    
    # Наличие квеста
    quest_mentions = char_soup.find_all(text=re.compile(r'quest', re.IGNORECASE))
    if len(quest_mentions) > 2:
        npc_score += 1
        if char_soup.find(['h2', 'h3'], string=re.compile(r'quest', re.IGNORECASE)):
            npc_score += 2
            character_info['has_quest'] = True
    
    # Указание на торговлю или услуги
    if 'sells' in page_text or 'offers' in page_text or 'shop' in page_text or 'service' in page_text:
        npc_score += 1
    
    # Упоминание взаимодействия с игроком
    interaction_terms = ['speak to', 'talk to', 'interact with', 'approach']
    for term in interaction_terms:
        if term in page_text:
            npc_score += 1
            break
    
    # NPC не может быть боссом или мини-боссом одновременно
    character_info['is_npc'] = not character_info['is_boss'] and not character_info['is_miniboss'] and npc_score >= 3
    
    # Определение базового типа персонажа
    if character_info['is_boss']:
        character_info['character_type'] = 'Boss'
    elif character_info['is_miniboss']:
        character_info['character_type'] = 'Mini-Boss'
    elif character_info['is_npc']:
        if 'merchant' in page_text or 'vendor' in page_text or 'shop' in page_text:
            character_info['character_type'] = 'Merchant NPC'
        elif character_info['has_quest']:
            character_info['character_type'] = 'Quest NPC'
        else:
            character_info['character_type'] = 'NPC'
    else:
        character_info['character_type'] = 'Regular Enemy'
    
    # Определение дружественности/враждебности
    if character_info['is_boss'] or character_info['is_miniboss']:
        character_info['is_hostile'] = True
        character_info['is_friendly'] = False
    elif character_info['is_npc']:
        hostile_words = ['hostile', 'enemy', 'invader', 'attacks', 'fight', 'aggro', 'aggressive']
        friendly_words = ['friendly', 'ally', 'merchant', 'vendor', 'helps', 'quest', 'assistance']
        
        hostility_score = sum(page_text.count(word) for word in hostile_words)
        friendly_score = sum(page_text.count(word) for word in friendly_words)
        
        # Проверка конкретных фраз
        if 'attack on sight' in page_text or 'hostile to player' in page_text:
            hostility_score += 3
        if 'friendly to player' in page_text or 'offers assistance' in page_text:
            friendly_score += 3
        
        character_info['is_hostile'] = hostility_score > friendly_score
        character_info['is_friendly'] = friendly_score >= hostility_score
    else:
        # Обычный враг по умолчанию враждебен
        character_info['is_hostile'] = True
        character_info['is_friendly'] = False
    
    # Если здоровье не найдено, сгенерируем примерное значение по типу
    if character_info['health'] == 0:
        if character_info['is_boss']:
            character_info['health'] = 10000 + (hash(character_info['name']) % 20000)
        elif character_info['is_miniboss']:
            character_info['health'] = 5000 + (hash(character_info['name']) % 5000)
        elif character_info['is_npc']:
            character_info['health'] = 200 + (hash(character_info['name']) % 300)
        else:
            character_info['health'] = 500 + (hash(character_info['name']) % 1500)
    
    characters_data.append(character_info)

# Сохранение данных в форматах JSON и CSV
with open('elden_ring_characters.json', 'w', encoding='utf-8') as f:
    json.dump(characters_data, f, ensure_ascii=False, indent=4)

df = pd.DataFrame(characters_data)
df.to_csv('elden_ring_characters.csv', index=False, encoding='utf-8')

print("Сбор данных завершен. Найдено:")
print(f"Боссов: {sum(1 for c in characters_data if c['is_boss'])}")
print(f"Мини-боссов: {sum(1 for c in characters_data if c['is_miniboss'])}")
print(f"NPC: {sum(1 for c in characters_data if c['is_npc'])}")
print(f"Другие персонажи: {sum(1 for c in characters_data if not c['is_boss'] and not c['is_miniboss'] and not c['is_npc'])}")