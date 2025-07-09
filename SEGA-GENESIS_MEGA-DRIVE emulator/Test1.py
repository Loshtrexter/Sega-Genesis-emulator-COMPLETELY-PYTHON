
import pygame
import tkinter as tk
from tkinter import filedialog

# ---------------- CPU68000 ----------------
class CPU68000:
    def __init__(self, memory_size=1024*1024):
        self.d = [0]*8
        self.a = [0]*8
        self.pc = 0
        self.memory = bytearray(memory_size)
        self.ccr = 0  # Condition Code Register (Z flag)
        self.a[7] = memory_size - 4  # SP init
        self.vdp = None

    def link_vdp(self, vdp):
        self.vdp = vdp

    def load_rom(self, rom_bytes):
        self.memory[0:len(rom_bytes)] = rom_bytes
        # Initial PC is at offset 4 in ROM header
        self.pc = int.from_bytes(self.memory[4:8], byteorder='big')

    def read_word(self, addr):
        return int.from_bytes(self.memory[addr:addr+2], 'big')

    def read_long(self, addr):
        return int.from_bytes(self.memory[addr:addr+4], 'big')

    def write_word(self, addr, value):
        self.memory[addr:addr+2] = value.to_bytes(2, 'big')

    def write_long(self, addr, value):
        self.memory[addr:addr+4] = value.to_bytes(4, 'big')

    def push_long(self, value):
        self.a[7] -= 4
        self.write_long(self.a[7], value)

    def pop_long(self):
        value = self.read_long(self.a[7])
        self.a[7] += 4
        return value

    def set_zero_flag(self, val):
        if val == 0:
            self.ccr |= 0x04
        else:
            self.ccr &= ~0x04

    def zero_flag_set(self):
        return (self.ccr & 0x04) != 0

    def ea_read(self, mode, reg, size):
        def sign_extend(val, bits):
            if val & (1 << (bits - 1)):
                return val | (~0 << bits)
            return val

        if mode == 0:  # Dn
            val = self.d[reg]
            if size == 1: return val & 0xFF
            if size == 2: return val & 0xFFFF
            return val
        elif mode == 1:  # An
            return self.a[reg]
        elif mode == 2:  # (An)
            addr = self.a[reg]
            if size == 1: return self.read_word(addr) & 0xFF
            if size == 2: return self.read_word(addr)
            if size == 4: return self.read_long(addr)
        elif mode == 3:  # (An)+
            addr = self.a[reg]
            if size == 1:
                val = self.read_word(addr) & 0xFF
                self.a[reg] += 1
            elif size == 2:
                val = self.read_word(addr)
                self.a[reg] += 2
            elif size == 4:
                val = self.read_long(addr)
                self.a[reg] += 4
            return val
        elif mode == 4:  # -(An)
            if size == 1: self.a[reg] -= 1
            elif size == 2: self.a[reg] -= 2
            elif size == 4: self.a[reg] -= 4
            addr = self.a[reg]
            if size == 1: return self.read_word(addr) & 0xFF
            if size == 2: return self.read_word(addr)
            if size == 4: return self.read_long(addr)
        elif mode == 5:  # (d16,An)
            disp = self.read_word(self.pc)
            self.pc += 2
            addr = (self.a[reg] + sign_extend(disp, 16)) & 0xFFFFFF
            if size == 1: return self.read_word(addr) & 0xFF
            if size == 2: return self.read_word(addr)
            if size == 4: return self.read_long(addr)
        elif mode == 6:  # (d8,An,Xn)
            ext = self.read_word(self.pc)
            self.pc += 2
            disp = ext & 0xFF
            if disp & 0x80: disp -= 0x100
            xn = (ext >> 12) & 7
            x_is_a = (ext >> 15) & 1
            scale = 1 << ((ext >> 9) & 3)
            idx_val = self.a[xn] if x_is_a else self.d[xn]
            addr = (self.a[reg] + disp + idx_val * scale) & 0xFFFFFF
            if size == 1: return self.read_word(addr) & 0xFF
            if size == 2: return self.read_word(addr)
            if size == 4: return self.read_long(addr)
        elif mode == 7:
            if reg == 0:  # (xxx).W
                addr = self.read_word(self.pc)
                self.pc += 2
                if size == 1: return self.read_word(addr) & 0xFF
                if size == 2: return self.read_word(addr)
                if size == 4: return self.read_long(addr)
            elif reg == 1:  # (xxx).L
                addr = self.read_long(self.pc)
                self.pc += 4
                if size == 1: return self.read_word(addr) & 0xFF
                if size == 2: return self.read_word(addr)
                if size == 4: return self.read_long(addr)
            elif reg == 2:  # (d16,PC)
                disp = self.read_word(self.pc)
                self.pc += 2
                addr = (self.pc + sign_extend(disp, 16)) & 0xFFFFFF
                if size == 1: return self.read_word(addr) & 0xFF
                if size == 2: return self.read_word(addr)
                if size == 4: return self.read_long(addr)
            elif reg == 3:  # (d8,PC,Xn)
                ext = self.read_word(self.pc)
                self.pc += 2
                disp = ext & 0xFF
                if disp & 0x80: disp -= 0x100
                xn = (ext >> 12) & 7
                x_is_a = (ext >> 15) & 1
                scale = 1 << ((ext >> 9) & 3)
                idx_val = self.a[xn] if x_is_a else self.d[xn]
                addr = (self.pc + disp + idx_val * scale) & 0xFFFFFF
                if size == 1: return self.read_word(addr) & 0xFF
                if size == 2: return self.read_word(addr)
                if size == 4: return self.read_long(addr)
            elif reg == 4:  # #imm
                if size == 1:
                    val = self.read_word(self.pc) & 0xFF
                    self.pc += 2
                    return val
                elif size == 2:
                    val = self.read_word(self.pc)
                    self.pc += 2
                    return val
                elif size == 4:
                    val = self.read_long(self.pc)
                    self.pc += 4
                    return val
        return 0

    def ea_write(self, mode, reg, size, value):
        def sign_extend(val, bits):
            if val & (1 << (bits - 1)):
                return val | (~0 << bits)
            return val

        if mode == 0:  # Dn
            if size == 1:
                self.d[reg] = (self.d[reg] & 0xFFFFFF00) | (value & 0xFF)
            elif size == 2:
                self.d[reg] = (self.d[reg] & 0xFFFF0000) | (value & 0xFFFF)
            else:
                self.d[reg] = value & 0xFFFFFFFF
        elif mode == 1:  # An
            self.a[reg] = value
        elif mode == 2:  # (An)
            addr = self.a[reg]
            if size == 1:
                w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                self.write_word(addr, w)
            elif size == 2:
                self.write_word(addr, value)
            elif size == 4:
                self.write_long(addr, value)
        elif mode == 3:  # (An)+
            addr = self.a[reg]
            if size == 1:
                w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                self.write_word(addr, w)
                self.a[reg] += 1
            elif size == 2:
                self.write_word(addr, value)
                self.a[reg] += 2
            elif size == 4:
                self.write_long(addr, value)
                self.a[reg] += 4
        elif mode == 4:  # -(An)
            if size == 1: self.a[reg] -= 1
            elif size == 2: self.a[reg] -= 2
            elif size == 4: self.a[reg] -= 4
            addr = self.a[reg]
            if size == 1:
                w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                self.write_word(addr, w)
            elif size == 2:
                self.write_word(addr, value)
            elif size == 4:
                self.write_long(addr, value)
        elif mode == 5:  # (d16,An)
            disp = self.read_word(self.pc)
            self.pc += 2
            addr = (self.a[reg] + sign_extend(disp, 16)) & 0xFFFFFF
            if size == 1:
                w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                self.write_word(addr, w)
            elif size == 2:
                self.write_word(addr, value)
            elif size == 4:
                self.write_long(addr, value)
        elif mode == 6:  # (d8,An,Xn)
            ext = self.read_word(self.pc)
            self.pc += 2
            disp = ext & 0xFF
            if disp & 0x80: disp -= 0x100
            xn = (ext >> 12) & 7
            x_is_a = (ext >> 15) & 1
            scale = 1 << ((ext >> 9) & 3)
            idx_val = self.a[xn] if x_is_a else self.d[xn]
            addr = (self.a[reg] + disp + idx_val * scale) & 0xFFFFFF
            if size == 1:
                w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                self.write_word(addr, w)
            elif size == 2:
                self.write_word(addr, value)
            elif size == 4:
                self.write_long(addr, value)
        elif mode == 7:
            if reg == 0:  # (xxx).W
                addr = self.read_word(self.pc)
                self.pc += 2
                if size == 1:
                    w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                    self.write_word(addr, w)
                elif size == 2:
                    self.write_word(addr, value)
                elif size == 4:
                    self.write_long(addr, value)
            elif reg == 1:  # (xxx).L
                addr = self.read_long(self.pc)
                self.pc += 4
                if size == 1:
                    w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                    self.write_word(addr, w)
                elif size == 2:
                    self.write_word(addr, value)
                elif size == 4:
                    self.write_long(addr, value)
            elif reg == 2:  # (d16,PC)
                disp = self.read_word(self.pc)
                self.pc += 2
                addr = (self.pc + sign_extend(disp, 16)) & 0xFFFFFF
                if size == 1:
                    w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                    self.write_word(addr, w)
                elif size == 2:
                    self.write_word(addr, value)
                elif size == 4:
                    self.write_long(addr, value)
            elif reg == 3:  # (d8,PC,Xn)
                ext = self.read_word(self.pc)
                self.pc += 2
                disp = ext & 0xFF
                if disp & 0x80: disp -= 0x100
                xn = (ext >> 12) & 7
                x_is_a = (ext >> 15) & 1
                scale = 1 << ((ext >> 9) & 3)
                idx_val = self.a[xn] if x_is_a else self.d[xn]
                addr = (self.pc + disp + idx_val * scale) & 0xFFFFFF
                if size == 1:
                    w = self.read_word(addr) & 0xFF00 | (value & 0xFF)
                    self.write_word(addr, w)
                elif size == 2:
                    self.write_word(addr, value)
                elif size == 4:
                    self.write_long(addr, value)

    def step(self):
        opcode = self.read_word(self.pc)
        self.pc += 2

        # Example: NOP, RTS, JSR, MOVE.W #imm,Dn, CMP.W, ADD.W, BRA, BEQ
        if opcode == 0x4E71:  # NOP
            pass
        elif opcode == 0x4E75:  # RTS
            self.pc = self.pop_long()
        elif opcode == 0x4EB9:  # JSR absolute long
            addr = self.read_long(self.pc)
            self.pc += 4
            self.push_long(self.pc)
            self.pc = addr
        elif (opcode & 0xF000) == 0x6000:  # BRA short
            offset = opcode & 0xFF
            if offset & 0x80:
                offset -= 0x100
            self.pc += offset
        elif (opcode & 0xFF00) == 0x6700:  # BEQ short
            offset = opcode & 0xFF
            if offset & 0x80:
                offset -= 0x100
            if self.zero_flag_set():
                self.pc += offset
        elif (opcode & 0xF1F8) == 0xB000:  # CMP.W Dn,Dm
            src = opcode & 0x7
            dest = (opcode >> 9) & 0x7
            val_src = self.d[src] & 0xFFFF
            val_dest = self.d[dest] & 0xFFFF
            result = (val_dest - val_src) & 0xFFFF
            self.set_zero_flag(result)
        elif (opcode & 0xF000) == 0x3000:  # MOVE.W #imm,Dn
            dest = (opcode >> 9) & 0x7
            value = self.read_word(self.pc)
            self.pc += 2
            self.d[dest] = value & 0xFFFF
            self.set_zero_flag(value)
        elif (opcode & 0xF1F8) == 0xD000:  # ADD.W Dn,Dm
            src = opcode & 0x7
            dest = (opcode >> 9) & 0x7
            result = (self.d[dest] + self.d[src]) & 0xFFFF
            self.d[dest] = result
            self.set_zero_flag(result)
        else:
            # Now you can call your new EA logic for more instructions!
            print(f"Unknown opcode {opcode:04X} at {self.pc-2:06X}")


# ---------------- VDP ----------------
class VDP:
    def __init__(self, screen, scale=2):
        self.screen = screen
        self.scale = scale

        self.vram = bytearray(64 * 1024)
        self.cram = [0]*64
        self.vsram = [0]*40
        self.registers = [0]*24
        self.status = 0

        self.tiles_x = 40
        self.tiles_y = 28
        self.tile_w = 8
        self.tile_h = 8

    def write_vram_word(self, addr, value):
        if 0 <= addr <= len(self.vram)-2:
            self.vram[addr] = (value >> 8) & 0xFF
            self.vram[addr+1] = value & 0xFF

    def write_cram_word(self, idx, value):
        if 0 <= idx < 64:
            self.cram[idx] = value & 0x1FF

    def get_rgb_from_cram(self, cram_val):
        r = ((cram_val >> 0) & 0x07) * 255 // 7
        g = ((cram_val >> 3) & 0x07) * 255 // 7
        b = ((cram_val >> 6) & 0x03) * 255 // 3
        return (r, g, b)

    def render_sega_splash(self):
        self.screen.fill((0,0,0))
        font = pygame.font.SysFont("Arial", 120, True)
        text = font.render("SEGA", True, (0,0,255))
        rect = text.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2))
        self.screen.blit(text, rect)

    def render(self):
        # Get horizontal and vertical scroll from registers for smooth scrolling
        hscroll = ((self.registers[0x0F] & 1) << 8) | self.registers[0x0E]
        vscroll = self.registers[0x10]

        base_tilemap_addr = (self.registers[0x0C] & 0x7F) * 0x800

        # Because of scroll, calculate pixel offset within tile (0-7)
        h_offset = hscroll % 8
        v_offset = vscroll % 8

        # Calculate starting tile offset in tilemap
        tile_x_start = hscroll // 8
        tile_y_start = vscroll // 8

        for screen_y in range(self.tiles_y + 1):  # +1 to fill gap from scrolling
            for screen_x in range(self.tiles_x + 1):
                tilemap_x = (tile_x_start + screen_x) % self.tiles_x
                tilemap_y = (tile_y_start + screen_y) % self.tiles_y

                entry_addr = base_tilemap_addr + ((tilemap_y * self.tiles_x + tilemap_x) * 2)
                if entry_addr+1 >= len(self.vram):
                    continue

                entry = (self.vram[entry_addr] << 8) | self.vram[entry_addr+1]

                tile_index = entry & 0x07FF
                flip_h = (entry >> 11) & 1
                flip_v = (entry >> 12) & 1
                palette_index = (entry >> 13) & 0x07

                tile_offset = tile_index * 32
                if tile_offset + 31 >= len(self.vram):
                    continue

                for row in range(8):
                    base = tile_offset + row * 4
                    plane0 = (self.vram[base] << 8) | self.vram[base+1]
                    plane1 = (self.vram[base+2] << 8) | self.vram[base+3]
                    plane2 = (self.vram[base+16] << 8) | self.vram[base+17]
                    plane3 = (self.vram[base+18] << 8) | self.vram[base+19]

                    for bit in range(7, -1, -1):
                        bit0 = (plane0 >> bit) & 1
                        bit1 = (plane1 >> bit) & 1
                        bit2 = (plane2 >> bit) & 1
                        bit3 = (plane3 >> bit) & 1
                        color_num = (bit3 << 3) | (bit2 << 2) | (bit1 << 1) | bit0

                        if color_num == 0:
                            continue

                        cram_index = palette_index * 16 + color_num
                        if cram_index >= len(self.cram):
                            cram_index = 0

                        color = self.get_rgb_from_cram(self.cram[cram_index])

                        # Calculate pixel pos on screen with scroll offset
                        px = bit if not flip_h else 7 - bit
                        py = row if not flip_v else 7 - row

                        draw_x = ((screen_x * self.tile_w + px) - h_offset) * self.scale
                        draw_y = ((screen_y * self.tile_h + py) - v_offset) * self.scale

                        pygame.draw.rect(self.screen, color, pygame.Rect(draw_x, draw_y, self.scale, self.scale))

# ---------------- Utility ----------------
def parse_rom_info(rom_bytes):
    title = rom_bytes[0x120:0x150].decode('ascii', errors='ignore').strip()
    region = rom_bytes[0x1F0:0x1F4].decode('ascii', errors='ignore').strip()
    region = {
        "J": "Japan", "U": "USA", "E": "Europe",
        "JU": "USA + Japan", "UE": "USA + Europe"
    }.get(region, region)
    return title, region

def draw_memory_view(screen, font, memory, start_addr):
    for i in range(12):
        line_addr = start_addr + i*4
        if line_addr + 4 <= len(memory):
            bytes_line = memory[line_addr:line_addr+4]
            hex_str = " ".join(f"{b:02X}" for b in bytes_line)
            line = f"{line_addr:06X}: {hex_str}"
            screen.blit(font.render(line, True, (180, 180, 180)), (10, 220 + i*22))

# ---------------- Main loop ----------------
root = tk.Tk()
root.withdraw()

pygame.init()
screen_w, screen_h = 640, 448
screen = pygame.display.set_mode((screen_w, screen_h))
pygame.display.set_caption("GEGHOGAN2 EMULATOR")
font = pygame.font.SysFont("Arial", 20)
big_font = pygame.font.SysFont("Arial", 80)
clock = pygame.time.Clock()

rom_data = None
rom_title = ""
rom_region = ""
cpu = None
vdp = None
running_mode = False
show_sega = True
sega_timer = 0
SEGA_SHOW_TIME_MS = 3000

def load_sonic_vram(vdp, rom):
    if len(rom) < 0x29000:
        return
    # Load tiles and tilemap for Sonic 1 from known ROM offsets
    vdp.vram[0x0000:0x8000] = rom[0x20000:0x28000]
    tilemap_base = (vdp.registers[0x0C] & 0x7F) * 0x800
    vdp.vram[tilemap_base:tilemap_base+0x1000] = rom[0x28000:0x29000]

    # Load a simple palette gradient for now
    for i in range(64):
        val = (i & 7) | ((i & 7) << 3) | ((i & 3) << 6)
        vdp.write_cram_word(i, val)

intro_sequence_done = False

while True:
    dt = clock.tick(60)
    screen.fill((0, 0, 0))

    if show_sega:
        if not vdp:
            vdp = VDP(screen, scale=1)
        vdp.render_sega_splash()
        sega_timer += dt
        if sega_timer > SEGA_SHOW_TIME_MS:
            show_sega = False
    else:
        if not intro_sequence_done:
            intro_sequence_done = True

        status_text = "Press SPACE to load ROM"
        if rom_data:
            status_text = "Running... Press SPACE to pause" if running_mode else "Paused. Press → to step, SPACE to run"

        screen.blit(font.render(status_text, True, (255, 255, 0)), (10, 10))
        screen.blit(font.render(f"Title: {rom_title}", True, (0, 255, 0)), (10, 40))
        screen.blit(font.render(f"Region: {rom_region}", True, (0, 255, 0)), (10, 70))
        screen.blit(font.render(f"PC: {cpu.pc:06X}" if cpu else "PC: ----", True, (255, 255, 255)), (10, 100))

        if rom_data and cpu and vdp:
            vdp.render()
            draw_memory_view(screen, font, cpu.memory, cpu.pc)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if rom_data is None:
                    path = filedialog.askopenfilename(
                        title="Load Sonic 1 ROM",
                        filetypes=[("Genesis ROMs", "*.bin *.gen *.md")]
                    )
                    if path:
                        with open(path, "rb") as f:
                            rom_data = f.read()
                        rom_title, rom_region = parse_rom_info(rom_data)
                        cpu = CPU68000()
                        vdp = VDP(screen, scale=1)
                        cpu.link_vdp(vdp)
                        cpu.load_rom(rom_data)
                        running_mode = False
                        load_sonic_vram(vdp, rom_data)
                else:
                    running_mode = not running_mode

            elif event.key == pygame.K_RIGHT and rom_data and not running_mode:
                cpu.step()

    if running_mode and cpu:
        # Run 500 CPU instructions per frame for speed
        for _ in range(500):
            cpu.step()

    pygame.display.flip()